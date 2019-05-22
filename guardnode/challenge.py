#!/usr/bin/env python3
import logging
from time import sleep
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from .daemon import DaemonThread
from .test_framework import util, address

def connect(args):
    return AuthServiceProxy("http://%s:%s@%s:%s"%
        (args.rpcuser, args.rpcpassword, args.rpcconnect, args.rpcport))

def asset_in_block(ocean, asset, block_height):
    block = ocean.getblock(ocean.getblockhash(block_height), False)
    rev_asset = util.bytes_to_hex_str(util.hex_str_to_bytes(asset)[::-1])
    return rev_asset in block

class Challenge(DaemonThread):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.ocean = connect(self.args)

        logging.basicConfig()
        logging.getLogger("BitcoinRPC").setLevel(logging.INFO)
        self.logger = logging.getLogger("Challenge")
        self.logger.setLevel(logging.INFO)

        # test valid hash
        util.assert_is_hash_string(self.args.challengeasset)
        assert(asset_in_block(self.ocean, self.args.challengeasset, 0))
        self.logger.info("Challenge asset OK")

        # TODO: api check to verify bid is successful
        util.assert_is_hash_string(self.args.bidtxid)
        self.logger.info("Bid txid OK")

        # test valid key and imported
        self.address = address.key_to_p2pkh_version(args.pubkey, args.addressprefix)
        validate = self.ocean.validateaddress(self.address)
        assert(validate['isvalid'] == True)
        assert(validate['ismine'] == True)
        self.logger.info("Key OK")

        self.ocean.signmessage(self.address, self.args.bidtxid)
        self.logger.info("Signing test OK")

    def run(self):
        last_block_height = 0
        while not self.stop_event.is_set():
            block_height = self.ocean.getblockcount()
            if block_height > last_block_height:
                self.logger.info("current block height: {}".format(block_height))
                if asset_in_block(self.ocean, self.args.challengeasset, block_height):
                    self.logger.info("challenge found at height: {}".format(block_height))
                last_block_height = block_height
            else:
                sleep(0.1) # seconds
