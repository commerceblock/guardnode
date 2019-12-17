#!/usr/bin/env python3

"""test methods of Challenge class

"""
import subprocess
import imp
import sys

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
from test_framework.key import CPubKey, CECKey
from test_framework.mininode import sha256
from guardnode.challenge import Challenge, asset_in_block
from guardnode.bid import *

# dummy Challenge instance to pass into functions for testing
class Args:
    def __init__(self,genesis,ocean):
        self.key = None
        self.ocean = ocean
        self.args = InputArgs()
        self.genesis = genesis
        self.service_ocean = ocean
        self.client_fee_pubkey = None
        self.rev_challengeasset = None
        self.logger = logging.getLogger("Guardnode")
    def set_key(self,addr):
        Challenge.set_key(self, addr)
    # dummy method returns None to prevent asset_in_block() proceeding to respond() while testing
    def asset_in_block(self,asset,block_height):
        return None

# dummy self.args class
class InputArgs():
    def __init__(self):
        self.serviceblocktime = 1

class ChallengeTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [["-txindex=1 -initialfreecoins=50000000000000", "-policycoins=50000000000000",
    "-permissioncoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-initialfreecoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-challengecoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-debug=1"] for i in range(2)]

    def setup_network(self, split=False):
        self.nodes = start_nodes(self.num_nodes, self.options.tmpdir, self.extra_args)
        connect_nodes_bi(self.nodes,0,1)
        self.is_network_split=False
        self.sync_all()

    def run_test(self):
        # init node
        self.nodes[0].importprivkey("cTnxkovLhGbp7VRhMhGThYt8WDwviXgaVAD8DjaVa5G5DApwC6tF") # assets location
        self.nodes[0].generate(101)
        self.sync_all()
        genesis = self.nodes[0].getblockhash(0)

        # Test check_for_request method
        args = Args(genesis, self.nodes[0])
        assert_equal(Challenge.check_for_request(args),False) # return False whenno request

        # Make request
        requesttxid = make_request(self.nodes[0])
        self.nodes[0].generate(1)
        assert_equal(len(self.nodes[0].getrequests()),1)

        # Test check_for_request method returns request
        args = Args(genesis, self.nodes[0])
        assert_equal(Challenge.check_for_request(args)["genesisBlock"], genesis) # return request

        # Make another request with different genesis
        blockcount = self.nodes[0].getblockcount()
        unspent = self.nodes[0].listunspent(1, 9999999, [], True, "PERMISSION")
        pubkey = self.nodes[0].validateaddress(self.nodes[0].getnewaddress())["pubkey"]
        new_genesis = "e9a934a8ae2587fbe6b661e69115a5b7b9d624d73a248e9b2bce15e7d1cd48eb"
        inputs = {"txid": unspent[0]["txid"], "vout": unspent[0]["vout"]}
        outputs = {"decayConst": 10, "endBlockHeight": blockcount+20, "fee": 1, "genesisBlockHash": new_genesis,
        "startBlockHeight": blockcount+10, "tickets": 10, "startPrice": 5, "value": unspent[0]["amount"], "pubkey": pubkey}
        tx = self.nodes[0].createrawrequesttx(inputs, outputs)
        signedtx = self.nodes[0].signrawtransaction(tx)
        txid = self.nodes[0].sendrawtransaction(signedtx["hex"])
        self.nodes[0].generate(1)
        assert_equal(len(self.nodes[0].getrequests()),2)

        # Check correct request fetched for each genesis
        assert_equal(Challenge.check_for_request(args)["genesisBlock"], genesis)
        args.genesis = new_genesis
        assert_equal(Challenge.check_for_request(args)["genesisBlock"],args.genesis)


        # Test gen_feepubkey() and set_key()
        args = Args(genesis, self.nodes[0])
        addr = Challenge.gen_feepubkey(args)
        assert_is_hex_string(args.client_fee_pubkey) # check exists
        # Check resulting priv key corresponds to fee pub key
        assert_equal(CPubKey(args.key.get_pubkey()).hex(),args.client_fee_pubkey)


        # Test asset_in_block()
        assets = []
        for issuance in self.nodes[0].listissuances(): # grab each asset
            assets.append(issuance["asset"])
        # test each asset identified in genesis
        for asset in assets:
            assert(asset_in_block(self.nodes[0], hex_str_rev_hex_str(asset), 0))
        self.nodes[0].generate(1)
        # test none found in empty block
        for asset in assets:
            assert_equal(asset_in_block(self.nodes[0], asset, self.nodes[0].getblockcount()), None)
        # test invalid asset argument size
        assert_equal(asset_in_block(self.nodes[0], None, 0), None)
        assert_equal(asset_in_block(self.nodes[0], 1234, 0), None)
        assert_equal(asset_in_block(self.nodes[0], 0, 0), None)


        # Test await_challenge()
        block_count = self.nodes[0].getblockcount()
        args.last_block_height = block_count
        request = {"endBlockHeight":block_count+2,"startBlockHeight":block_count+1,"txid":"1234"}
        # Check request not yet started
        assert_equal(Challenge.await_challenge(args, request),True)
        # Check Challenge asset check called
        self.nodes[0].generate(1)
        assert_equal(Challenge.await_challenge(args, request),None)
        # Check request ended
        self.nodes[0].generate(2)
        assert_equal(Challenge.await_challenge(args, request),False)


if __name__ == '__main__':
    ChallengeTest().main()
