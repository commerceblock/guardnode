#!/usr/bin/env python3
import logging
import json
import requests
import sys
import base58
from time import sleep
from .daemon import DaemonThread
from .qa.tests.test_framework import util, address, key, authproxy
from .bid import BidHandler

def connect(host, user, pw):
    return authproxy.AuthServiceProxy("http://%s:%s@%s"% (user, pw, host))

def asset_in_block(ocean, asset, block_height):
    block = ocean.getblock(ocean.getblockhash(block_height), True)
    if "tx" in block:
        for txid in block['tx']:
            tx = ocean.getrawtransaction(txid, False)
            if asset in tx:
                return txid
    return None

def get_challenge_asset(ocean):
    genesis_block = ocean.getblock(ocean.getblockhash(0))
    for txid in genesis_block["tx"]:
        tx = ocean.getrawtransaction(txid, True)
        for vout in tx["vout"]:
            if "assetlabel" in vout and vout["assetlabel"] == "CHALLENGE":
                return vout["asset"]
    self.logger.error("No Challenge asset found in client chain")
    sys.exit(1)

class Challenge(DaemonThread):
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
        self.rev_challengeasset = util.hex_str_rev_hex_str(self.args.challengeasset)

        # If not set then generate fresh
        self.client_fee_pubkey = None
        self.genfeepubkeys = True;
        self.key = None
        if args.bidpubkey is not None:
            self.client_fee_pubkey = args.bidpubkey
            self.genfeepubkeys = False;
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

            self.logger.info("Fee address: {} and pubkey: {}".format(address, self.client_fee_pubkey))
        else:
            self.logger.info("Fee pubkey will be freshly generated each bid")

        # Init bid handler
        self.bidhandler = BidHandler(self.service_ocean, args.bidlimit, args.bidfee)

    # store private key for signing
    def set_key(self, addr):
        priv = self.service_ocean.dumpprivkey(addr)
        decoded = base58.b58decode(priv)[1:-5] # check for compressed or not
        self.key = key.CECKey()
        self.key.set_secretbytes(decoded)
        self.key.set_compressed(True)

    # gen new feepubkey and set self.key
    def gen_feepubkey(self):
        address = self.service_ocean.getnewaddress()
        self.set_key(address)
        self.client_fee_pubkey = self.service_ocean.validateaddress(address)["pubkey"]

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

    def run(self):
        last_block_height = 0
        while not self.stop_event.is_set():
            requests = self.service_ocean.getrequests(self.genesis)
            if len(requests) > 0:
                request = requests[0]
                self.logger.info("Found request: {}".format(request))
                if self.genfeepubkeys: # Gen new pubkey if required
                    self.gen_feepubkey()
                bid_txid = self.bidhandler.do_request_bid(request, self.client_fee_pubkey)
                if bid_txid is not None:
                    self.logger.info("Bid {} submitted".format(bid_txid))
                    while not self.stop_event.is_set():
                        try:
                            block_height = self.ocean.getblockcount()
                            if block_height > request["endBlockHeight"]:
                                self.logger.info("Request {} ended".format(request["txid"]))
                                break
                            elif block_height < request["startBlockHeight"]:
                                self.logger.info("Request {} not started yet".format(request["txid"]))
                                sleep(self.args.serviceblocktime)
                                continue
                            elif block_height > last_block_height:
                                self.logger.info("current block height: {}".format(block_height))
                                txid = asset_in_block(self.ocean, self.rev_challengeasset, block_height)
                                if txid != None:
                                    self.logger.info("challenge found at height: {}".format(block_height))
                                    self.respond(bid_txid, txid)
                                last_block_height = block_height
                        except Exception as e:
                            self.logger.error(e)
                            self.error = e
                        sleep(0.1) # seconds
                else:
                    sleep(self.args.serviceblocktime)
            else:
                self.logger.info("No active requests for genesis: {}".format(self.genesis))
                sleep(self.args.serviceblocktime)
