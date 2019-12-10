#!/usr/bin/env python3

"""test input args perform check correctly

"""
import subprocess


from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *

WAIT_FOR_ERROR_TIME = 0.5

class InputArgHandlingTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.extra_args = [["-txindex=1 -initialfreecoins=50000000000000", "-policycoins=50000000000000",
    "-permissioncoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-initialfreecoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-challengecoinsdestination=76a91415de997afac9857dc97cdd43803cf1138f3aaef788ac",
    "-debug=1"]]

    def setup_network(self, split=False):
        self.nodes = start_nodes(self.num_nodes, self.options.tmpdir, self.extra_args)
        self.is_network_split=False
        self.sync_all()

    def run_test(self):
        # init node
        self.nodes[0].importprivkey("cTnxkovLhGbp7VRhMhGThYt8WDwviXgaVAD8DjaVa5G5DApwC6tF")
        self.nodes[0].generate(101)
        # Make request
        addr = self.nodes[0].getnewaddress()
        priv = self.nodes[0].dumpprivkey(addr)
        pubkey = self.nodes[0].validateaddress(addr)["pubkey"]
        genesis = self.nodes[0].getblockhash(0)
        unspent = self.nodes[0].listunspent(1, 9999999, [], True, "PERMISSION")
        inputs = {"txid": unspent[0]["txid"], "vout": unspent[0]["vout"]}
        outputs = {"decayConst": 10, "endBlockHeight": 120, "fee": 1, "genesisBlockHash": genesis,
        "startBlockHeight": 110, "tickets": 10, "startPrice": 5, "value": unspent[0]["amount"], "pubkey": pubkey}
        tx = self.nodes[0].createrawrequesttx(inputs, outputs)
        signedtx = self.nodes[0].signrawtransaction(tx)
        txid = self.nodes[0].sendrawtransaction(signedtx["hex"])
        assert(txid in self.nodes[0].getrawmempool())

        # TODO: tests for all input arg checks
        # Test error for bad bidpubkey
        _, err = start_guardnode_await_error(WAIT_FOR_ERROR_TIME,["--bidpubkey","--nodelogfile",log_filename(self.options.tmpdir,0,"debug.log")])
        assert(b'expected one argument' in err)
        _, err = start_guardnode_await_error(WAIT_FOR_ERROR_TIME,["--bidpubkey","12345","--nodelogfile",log_filename(self.options.tmpdir,0,"debug.log")])
        assert(b'Error: Odd-length string' in err)

        # Test err on no requests
        _, err = start_guardnode_await_error(WAIT_FOR_ERROR_TIME, ["--nodelogfile", log_filename(self.options.tmpdir,0,"debug.log")])
        assert(b'No active requests for genesis:' in err)
        self.nodes[0].generate(1)
        assert_equal(len(self.nodes[0].getrequests()),1)

        # Test bid made correctly
        bidaddr = self.nodes[0].getnewaddress()
        bidpubkey = self.nodes[0].validateaddress(bidaddr)["pubkey"]
        guardnode = start_guardnode(["--nodelogfile", log_filename(self.options.tmpdir,0,"debug.log"),"--bidpubkey",bidpubkey])
        time.sleep(4) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        bidtxid1 = self.nodes[0].getrequestbids(txid)["bids"][0]["txid"] # check bid exists

        # Test next bid uses TX_LOCKED_MULTISIG output => uses previous bids utxo
        self.nodes[0].generate(19) # request over
        assert(not self.nodes[0].getrequests())
        # new request
        inputs = {"txid": unspent[1]["txid"], "vout": unspent[1]["vout"]}
        outputs = {"decayConst": 10, "endBlockHeight": 140, "fee": 1, "genesisBlockHash": genesis,
        "startBlockHeight": 130, "tickets": 10, "startPrice": 4, "value": unspent[1]["amount"], "pubkey": pubkey}
        tx = self.nodes[0].createrawrequesttx(inputs, outputs)
        signedtx = self.nodes[0].signrawtransaction(tx)
        txid = self.nodes[0].sendrawtransaction(signedtx["hex"])
        assert(txid in self.nodes[0].getrawmempool())
        self.nodes[0].generate(1)
        time.sleep(4) # give time for guardnode to make bid
        self.nodes[0].generate(1)

        # check bid2 input is bid1 output
        bidtxid2 = self.nodes[0].getrequestbids(txid)["bids"][0]["txid"]
        bidtx2 = self.nodes[0].decoderawtransaction(self.nodes[0].getrawtransaction(bidtxid2))
        assert_equal(bidtxid1,bidtx2["vin"][0]["txid"])

        # Test bid made without TX_LOCKED_MULTISIG output by increasing bid amount
        # to greater than TX_LOCKED_MULTISIG outputs value
        self.nodes[0].generate(19) # request over
        assert(not self.nodes[0].getrequests())
        # new request
        inputs = {"txid": unspent[2]["txid"], "vout": unspent[2]["vout"]}
        outputs = {"decayConst": 10, "endBlockHeight": 160, "fee": 1, "genesisBlockHash": genesis,
        "startBlockHeight": 150, "tickets": 10, "startPrice": 5, "value": unspent[2]["amount"], "pubkey": pubkey}
        tx = self.nodes[0].createrawrequesttx(inputs, outputs)
        signedtx = self.nodes[0].signrawtransaction(tx)
        txid = self.nodes[0].sendrawtransaction(signedtx["hex"])
        assert(txid in self.nodes[0].getrawmempool())
        self.nodes[0].generate(1)
        time.sleep(4) # give time for guardnode to make bid
        self.nodes[0].generate(1)

        # check bid exists and inputs utxo was not of type lockedmultisig
        bidtxid3 = self.nodes[0].getrequestbids(txid)["bids"][0]["txid"]
        bidtx3 = self.nodes[0].decoderawtransaction(self.nodes[0].getrawtransaction(bidtxid2))
        # to check if not type lockedmultisig: non bid vout value should be
        # change from initial free coin transaction since all other utxos are
        # lockedmultisig
        vout = 1 if bidtx3["vout"][0]["value"] == 5 else 0
        assert_greater_than(20999, bidtx3["vout"][vout]["value"])


if __name__ == '__main__':
    InputArgHandlingTest().main()
