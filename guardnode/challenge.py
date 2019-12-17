#!/usr/bin/env python3
import logging
import json
import requests
import sys
import base58
from time import sleep
from .daemon import DaemonThread
from .bid import BidHandler
from .qa.tests.test_framework import util, address, key, authproxy

def connect(host, user, pw):
    return authproxy.AuthServiceProxy("http://%s:%s@%s"% (user, pw, host))

# Find assetid for chains challenge asset
def get_challenge_asset(ocean):
    genesis_block = ocean.getblock(ocean.getblockhash(0))
    for txid in genesis_block["tx"]:
        tx = ocean.getrawtransaction(txid, True)
        for vout in tx["vout"]:
            if "assetlabel" in vout and vout["assetlabel"] == "CHALLENGE":
                return vout["asset"]
    return False

# Find if assetid in given block
def asset_in_block(ocean, asset, block_height):
    if asset == None or len(str(asset)) < 64:    # method may return true for non-assetid valuesc (such as None or 0)
        return None
    block = ocean.getblock(ocean.getblockhash(block_height), True)
    if "tx" in block:
        for txid in block['tx']:
            tx = ocean.getrawtransaction(txid, False)
            if asset in tx:
                return txid
    return None

class Challenge(DaemonThread):
    # store private key for signing
    def set_key(self, addr):
        priv = self.service_ocean.dumpprivkey(addr)
        decoded = base58.b58decode(priv)[1:-5] # check for compressed or not
        self.key = key.CECKey()
        self.key.set_secretbytes(decoded)
        self.key.set_compressed(True)

    # gen new feepubkey and set self.key, returns corresponding address
    def gen_feepubkey(self):
        address = self.service_ocean.getnewaddress()
        self.set_key(address)
        self.client_fee_pubkey = self.service_ocean.validateaddress(address)["pubkey"]
        return address

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.ocean = connect(self.args.rpchost, self.args.rpcuser, self.args.rpcpass)
        self.genesis = self.ocean.getblockhash(0)
        self.service_ocean = connect(self.args.servicerpchost, self.args.servicerpcuser, self.args.servicerpcpass)
        self.url = "{}/challengeproof".format(self.args.challengehost)

        logging.getLogger("BitcoinRPC")
        self.logger = logging.getLogger("Challenge")

        # get challenge asset hash
        self.args.challengeasset = get_challenge_asset(self.ocean)
        try:
            self.rev_challengeasset = util.hex_str_rev_hex_str(self.args.challengeasset)
        except AttributeError: # if self.args.challengeasset == None
            self.logger.error("No Challenge asset found in client chain")
            sys.exit(1)

        # bidpubkey:
        # - if set then use for each bid
        # - if not set generate new and use for each bid
        # - if --uniquebidpubkeys set ignore --bidpubkey and generate new key for each bid
        # self.client_fee_pubkey = None
        if self.args.uniquebidpubkeys:
            self.uniquebidpubkeys = True
            self.logger.info("Fee pubkey will be freshly generated each bid")
        else:
            self.uniquebidpubkeys = False
            if args.bidpubkey is None:
                addr = self.gen_feepubkey()
            else:
                self.client_fee_pubkey = args.bidpubkey
                # get address prefix
                self.args.nodeaddrprefix = self.ocean.getsidechaininfo()["addr_prefixes"]["PUBKEY_ADDRESS"]
                if not hasattr(self.args, 'nodeaddrprefix'):
                    self.logger.error("Error getting address prefix - check node version")
                    sys.exit(1)
                # test valid key and imported
                addr = address.key_to_p2pkh_version(self.client_fee_pubkey, args.nodeaddrprefix)
                validate = self.ocean.validateaddress(addr)
                if validate['ismine'] == False:
                    self.logger.error("Key for address {} is missing from the wallet".format(addr))
                    sys.exit(1)
                # set self.key for signing
                self.set_key(addr)
            self.logger.info("Fee address: {} and pubkey: {}".format(addr, self.client_fee_pubkey))

        # Init bid handler
        self.bidhandler = BidHandler(self.service_ocean, args.bidlimit, args.bidfee)

    # MAIN RUN METHODS
    def check_for_request(self):
        requests = self.service_ocean.getrequests(self.genesis)
        if len(requests) > 0:
            self.logger.info("Found request: {}".format(requests[0]))
            return requests[0]
        return False

    # await request and place bid
    def run(self):
        self.last_block_height = 0
        # Wait for request
        while not self.stop_event.is_set():
            request = self.check_for_request()
            if request:
                if self.uniquebidpubkeys:
                    self.gen_feepubkey() # Gen new pubkey if required
                bid_txid = self.bidhandler.do_request_bid(request, self.client_fee_pubkey)
                if bid_txid is not None: # bid tx sent
                    while not self.stop_event.is_set(): # Wait for challenge on bid
                        if not self.await_challenge(request):
                            break   # request ended
                else:
                    sleep(self.args.serviceblocktime)
            else:
                self.logger.info("No active requests for genesis: {}".format(self.genesis))
                sleep(self.args.serviceblocktime)

    # Wait for challenge. Return False if service period over, respond to challenge if found
    def await_challenge(self, request):
        try:
            block_height = self.ocean.getblockcount()
            if block_height > request["endBlockHeight"]:
                self.logger.info("Request {} ended".format(request["txid"]))
                return False
            elif block_height < request["startBlockHeight"]:
                self.logger.info("Request {} not started yet".format(request["txid"]))
                sleep(self.args.serviceblocktime)
                return True
            elif block_height > self.last_block_height:
                self.logger.info("Current block height: {}".format(block_height))
                txid = asset_in_block(self.ocean, self.rev_challengeasset, block_height)
                if txid != None:
                    self.logger.info("Challenge found at height: {}".format(block_height))
                    self.respond(bid_txid, txid)
                    self.last_block_height = block_height
        except Exception as e:
            self.logger.error(e)
            self.error = e
            sleep(0.1) # seconds

    # respond to challenge
    def respond(self, bid_txid, txid):
        sig_hex = util.bytes_to_hex_str(self.key.sign(util.hex_str_to_rev_bytes(txid)))

        data = '{{"txid": "{}", "pubkey": "{}", "hash": "{}", "sig": "{}"}}'.\
            format(bid_txid, self.client_fee_pubkey, txid, sig_hex)
        headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
        try:
            r = requests.post(self.url, data=data, headers=headers)
        except Exception as e:
            self.logger.error(e)
            self.logger.error("Could not connect to coordinator to send response data:\n{}".format(data))
            return

        self.logger.info("response sent\nsignature:\n{}\ntxid:\n{}".format(sig_hex, txid))
        if r.status_code != 200:
            self.logger.error(r.content)
