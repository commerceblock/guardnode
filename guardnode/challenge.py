#!/usr/bin/env python3
import logging
import json
import requests
import sys
import base58
from time import sleep
from .daemon import DaemonThread
from .test_framework import util, address, key, authproxy

def connect(args):
    return authproxy.AuthServiceProxy("http://%s:%s@%s:%s"%
        (args.rpcuser, args.rpcpassword, args.rpcconnect, args.rpcport))

def asset_in_block(ocean, asset, block_height):
    block = ocean.getblock(ocean.getblockhash(block_height), True)
    if "tx" in block:
        for txid in block['tx']:
            tx = ocean.getrawtransaction(txid, False)
            if asset in tx:
                return txid
    return None

class Challenge(DaemonThread):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.ocean = connect(self.args)
        self.url = "http://{}/challengeproof".format(self.args.challengehost)

        logging.basicConfig()
        logging.getLogger("BitcoinRPC").setLevel(logging.INFO)
        self.logger = logging.getLogger("Challenge")
        self.logger.setLevel(logging.INFO)

        # test valid asset hash
        util.assert_is_hash_string(self.args.challengeasset)
        self.rev_challengeasset = util.hex_str_rev_hex_str(self.args.challengeasset)
        if asset_in_block(self.ocean, self.rev_challengeasset, 0) == None:
            self.logger.error("Asset {} not found in genesis block".format(self.args.challengeasset))
            sys.exit(1)

        # test valid bid txid
        util.assert_is_hash_string(self.args.bidtxid)

        # test valid key and imported
        self.address = address.key_to_p2pkh_version(args.bidpubkey, args.nodeaddrprefix)
        validate = self.ocean.validateaddress(self.address)
        if validate['ismine'] == False:
            self.logger.error("Key for address {} is missing from the wallet".format(self.address))
            sys.exit(1)

        # set key for signing
        priv = self.ocean.dumpprivkey(self.address)
        decoded = base58.b58decode(priv)[1:-5] # check for compressed or not
        self.key = key.CECKey()
        self.key.set_secretbytes(decoded)
        self.key.set_compressed(True)

    def respond(self, txid):
        sig_hex = util.bytes_to_hex_str(self.key.sign(util.hex_str_to_rev_bytes(txid)))

        data = '{{"txid": "{}", "pubkey": "{}", "hash": "{}", "sig": "{}"}}'.\
            format(self.args.bidtxid, self.args.bidpubkey, txid, sig_hex)
        headers = {'content-type': 'application/json', 'Accept-Charset': 'UTF-8'}
        r = requests.post(self.url, data=data, headers=headers)

        self.logger.info("response sent\nsignature:\n{}\ntxid:\n{}".format(sig_hex, txid))
        if r.status_code != 200:
            self.logger.error(r.content)

    def run(self):
        last_block_height = 0
        while not self.stop_event.is_set():
            try:
                block_height = self.ocean.getblockcount()
                if block_height > last_block_height:
                    self.logger.info("current block height: {}".format(block_height))
                    txid = asset_in_block(self.ocean, self.rev_challengeasset, block_height)
                    if txid != None:
                        self.logger.info("challenge found at height: {}".format(block_height))
                        self.respond(txid)
                    last_block_height = block_height
            except Exception as e:
                self.logger.error(e)
                self.ocean = connect(self.args)
            sleep(0.1) # seconds
