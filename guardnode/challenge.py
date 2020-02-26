#!/usr/bin/env python3
import logging
import json
import requests
import sys
import base58
from time import sleep
from .daemon import DaemonThread
from .bid import BidHandler
from .qa.tests.test_framework.util import hex_str_rev_hex_str, bytes_to_hex_str, hex_str_to_rev_bytes
from .qa.tests.test_framework.address import key_to_p2pkh_version
from .qa.tests.test_framework.key import CECKey
from .qa.tests.test_framework.authproxy import AuthServiceProxy

expos = list(map(lambda n: n**2,range(1,15)))

def connect(host, user, pw, logger):
    conn = AuthServiceProxy("http://%s:%s@%s"% (user, pw, host))
    try: # Check connection
        _ = conn.getinfo()
    except Exception as e:
        if "Connection refused" in str(e):
            logger.error("Node at "+host+" not reachable.")
        elif "401 Unauthorized" in str(e):
            logger.error("Authorisation failed for rpc connection to node "+host+".")
        else: raise(e)
        exit(0)
    return conn

# return assetid of challenge asset in given chain
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
        priv = self.ocean.dumpprivkey(addr)
        decoded = base58.b58decode(priv)[1:-5] # check for compressed or not
        self.key = CECKey()
        self.key.set_secretbytes(decoded)
        self.key.set_compressed(True)

    # given fee pubkey set corresponding challenge signing key
    def set_key_from_feepubkey(self, feepubkey):
        # set key to feepubkey's private key for signing of challenges
        self.client_fee_pubkey = feepubkey
        addr = key_to_p2pkh_version(feepubkey, self.nodeaddrprefix)
        self.set_key(addr)
        self.logger.info("Challenge signing key updated.")

    # gen new feepubkey and set self.key, returns corresponding address
    def gen_feepubkey(self):
        address = self.ocean.getnewaddress()
        self.set_key(address)
        self.client_fee_pubkey = self.ocean.validateaddress(address)["pubkey"]
        return address

    # Check if wallet has made previous bid which is still active. Prevents bidding
    # twice in the event of guardnode shut down in the middle of a service period.
    # Return bid txid if found, None otherwise
    def check_for_bid_from_wallet(self):
        try:
            # check for bids in currently active request
            bids = self.service_ocean.getrequestbids(self.request["txid"])["bids"]

            # Get transactions made since request tx was confirmed
            request_age = self.service_ocean.getblockcount() - self.request["confirmedBlockHeight"] + 1 # in blocks
            txs = self.service_ocean.listunspent(0,request_age,[],True)

            # Search for bid tx in all txs made since request confirmed
            for tx in txs:
                if tx["confirmations"] == 0: # check if unconfirmed tx is bid
                    tx = self.service_ocean.getrawtransaction(tx["txid"],True)
                    # check if request txid in any tx output scriptPubKey
                    for vout in tx["vout"]:
                        if hex_str_rev_hex_str(self.request["txid"]) in vout["scriptPubKey"]["hex"]:
                            self.logger.info("Previously made bid found. Txid: {}".format(tx["txid"]))
                            # int + OP_CHECKMULTISIG = 12 bytes up to 12+66 byte pubkey
                            bid_feepubkey = vout["scriptPubKey"]["hex"][12:78]
                            self.set_key_from_feepubkey(bid_feepubkey)
                            return tx["txid"]
                for bid in bids: # quicker to simply compare txids for confirmed txs
                    if tx["txid"] == bid["txid"]:
                        self.logger.info("Previously made bid found: {}".format(bid))
                        self.set_key_from_feepubkey(bid["feePubKey"])
                        return bid["txid"]
            return None
        except Exception:
            return None

    def __init__(self, args):
        super().__init__()
        self.args = args
        logging.getLogger("BitcoinRPC")
        self.logger = logging.getLogger("Challenge")
        self.ocean = connect(self.args.rpchost, self.args.rpcuser, self.args.rpcpass,self.logger)
        self.service_ocean = connect(self.args.servicerpchost, self.args.servicerpcuser, self.args.servicerpcpass,self.logger)
        self.no_request_msg_count = 0
        # if new node started give time for it to catch up
        while not hasattr(self,'genesis'):
            try:
                self.genesis = self.ocean.getblockhash(0)
            except Exception as e:
                if "Loading block index..." in str(e):
                    sleep(5) # wait for node to catch up
                    self.logger.error("Waiting for node to sync...")
                else: raise(e)
        self.url = "{}/challengeproof".format(self.args.challengehost)
        # get challenge asset hash
        self.args.challengeasset = get_challenge_asset(self.ocean)
        try:
            self.rev_challengeasset = hex_str_rev_hex_str(self.args.challengeasset)
        except AttributeError: # if self.args.challengeasset == None
            self.logger.error("No Challenge asset found in client chain")
            sys.exit(1)

        # get address prefix
        self.nodeaddrprefix = self.ocean.getsidechaininfo()["addr_prefixes"]["PUBKEY_ADDRESS"]
        if not hasattr(self, 'nodeaddrprefix'):
            self.logger.error("Error getting address prefix - check node version")
            sys.exit(1)

        # bidpubkey:
        # - if set then use for each bid
        # - if not set generate new and use for each bid
        # - if --uniquebidpubkeys set ignore --bidpubkey and generate new key for each bid
        if self.args.uniquebidpubkeys:
            self.uniquebidpubkeys = True
            self.logger.info("Fee pubkey will be freshly generated each bid")
        else:
            if args.bidpubkey is None:
                addr = self.gen_feepubkey()
            else:
                self.client_fee_pubkey = args.bidpubkey
                # test valid key and imported
                addr = key_to_p2pkh_version(self.client_fee_pubkey, self.nodeaddrprefix)
                validate = self.ocean.validateaddress(addr)
                if validate['ismine'] == False:
                    self.logger.error("Key for address {} is missing from the wallet".format(addr))
                    sys.exit(1)
                # set self.key for signing
                self.set_key(addr)
            self.logger.info("Fee address: {} and pubkey: {}".format(addr, self.client_fee_pubkey))

        # initial check for request and previously made bid
        self.request = None
        self.check_for_request()
        self.bid_txid = self.check_for_bid_from_wallet()

        # Init bid handler
        self.bidhandler = BidHandler(self.service_ocean, args.bidlimit)


    # Main loop: await request. Sub loop: run search for challenge
    def run(self):
        self.last_block_height = 0
        # Wait for request
        while not self.stop_event.is_set():
            if self.check_for_request():
                self.no_request_msg_count = 0
                if hasattr(self,"uniquebidpubkeys"):
                    self.gen_feepubkey() # Gen new pubkey if required
                if self.check_ready_for_bid():
                    self.bid_txid = self.bidhandler.do_request_bid(self.request, self.client_fee_pubkey)
                if self.bid_txid is not None: # bid tx sent
                    while not self.stop_event.is_set(): # Wait for challenge on bid
                        if not self.await_challenge():
                            break   # request ended
                        sleep(1) # seconds
                else:
                    sleep(self.args.serviceblocktime)
            else:
                self.no_request_msg_count += 1
                if self.no_request_msg_count in expos: # gradually get more quiet
                    self.logger.info("No active requests for genesis: {}.".format(self.genesis))
                sleep(self.args.serviceblocktime)

    # look for and return active request in service chain
    def check_for_request(self):
        try:
            requests = self.service_ocean.getrequests(self.genesis)
            if len(requests) > 0:
                if not self.request == requests[0]:
                    self.request = requests[0]
                    self.logger.info("Found request: {}".format(requests[0]))
                return True
        except Exception as e:
            self.logger.error(e)
            self.error = e
        return False

    # Check if ready for bid to be made, otherwise return false
    def check_ready_for_bid(self):
        if not self.request:
            return False

        try:
            # bid already made for current request
            requestbids = self.service_ocean.getrequestbids(self.request["txid"])["bids"]
            if any(bid["txid"] == self.bid_txid for bid in requestbids):
                return False

            # no tickets left
            num_bids = len(self.service_ocean.getrequestbids(self.request["txid"])["bids"])
            if num_bids >= self.request["numTickets"]:
                self.logger.warn("No tickets left on this auction.")
                return False
        except Exception: # thrown if no bids on request -> ready for bid
            pass
        # otherwise bid
        return True

    # Wait for challenge. Return False if service period over, True to continue looping.
    # Respond to challenge if found
    def await_challenge(self):
        try:
            block_height = self.service_ocean.getblockcount()
            if block_height >= self.request["endBlockHeight"]:
                self.logger.info("Request {} ended".format(self.request["txid"]))
                self.request = None
                self.bid_txid = None
                return False
            elif block_height < self.request["startBlockHeight"]:
                self.logger.info("Request {} not started yet".format(self.request["txid"]))
                sleep(self.args.serviceblocktime)
            elif block_height > self.last_block_height:
                self.logger.info("Current block height: {}".format(block_height))
                challenge_txid = asset_in_block(self.ocean, self.rev_challengeasset, block_height)
                if challenge_txid != None:
                    self.logger.info("Challenge found at height: {}".format(block_height))
                    self.respond(challenge_txid)
                self.last_block_height = block_height
            return True
        except Exception as e:
            self.logger.error(e)
            self.error = e

    # respond to challenge
    def respond(self, challenge_txid):
        data, headers = self.generate_response(challenge_txid)
        try:
            r = requests.post(self.url, data=data, headers=headers)
        except Exception as e:
            self.logger.error(e)
            self.logger.error("Could not connect to coordinator to send response data:\n{}".format(data))
            return

        self.logger.info("Response sent\nsignature:\n{}\ntxid:\n{}".format(data[data.find("sig")+7:-2], challenge_txid))
        if r.status_code != 200:
            self.logger.error(r.content)

    def generate_response(self, challenge_txid):
        sig_hex = bytes_to_hex_str(self.key.sign(hex_str_to_rev_bytes(challenge_txid)))

        data = '{{"txid": "{}", "pubkey": "{}", "hash": "{}", "sig": "{}"}}'.\
        format(self.bid_txid, self.client_fee_pubkey, challenge_txid, sig_hex)
        headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}

        return data, headers
