#!/usr/bin/env python3
import logging
from time import sleep
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from .daemon import DaemonThread
from .test_framework import util, address

def connect(args):
    return AuthServiceProxy("http://%s:%s@%s:%s"%
        (args.rpcuser, args.rpcpassword, args.rpcconnect, args.rpcport))

class Challenge(DaemonThread):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.ocean = connect(self.args)

        logging.basicConfig()
        logging.getLogger("BitcoinRPC").setLevel(logging.DEBUG)
        self.logger = logging.getLogger("Challenge")
        self.logger.setLevel(logging.INFO)

        # test valid hash
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
        while not self.stop_event.is_set():
            sleep(1)
