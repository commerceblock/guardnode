#!/usr/bin/env python3

"""test input args perform check correctly

"""
import subprocess


from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *

WAIT_FOR_ERROR_TIME = 0.5

class BiddingTest(BitcoinTestFramework):

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
        genesis = self.nodes[0].getblockhash(0)

        # Make request
        requesttxid = make_request(self.nodes[0])

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

        bidaddr = self.nodes[0].getnewaddress()
        bidpubkey = self.nodes[0].validateaddress(bidaddr)["pubkey"]
        guardnode = start_guardnode(["--nodelogfile", log_filename(self.options.tmpdir,0,"debug.log"),"--bidpubkey",bidpubkey])

        # Test bid placed
        time.sleep(2) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        # check bid exists
        bidtxid1 = self.nodes[0].getrequestbids(requesttxid)["bids"][0]["txid"]

        # Test next bid uses TX_LOCKED_MULTISIG output => uses previous bids utxo
        self.nodes[0].generate(19) # request over
        assert(not self.nodes[0].getrequests())
        requesttxid = make_request(self.nodes[0],4) # new request with price 4 to ensure TX_LOCKED_MULTISIG output is used
        self.nodes[0].generate(1)
        time.sleep(2) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        # check bid2 input is bid1 output
        bidtxid2 = self.nodes[0].getrequestbids(requesttxid)["bids"][0]["txid"]
        bidtx2 = self.nodes[0].decoderawtransaction(self.nodes[0].getrawtransaction(bidtxid2))
        assert_equal(len(bidtx2["vin"]),1)
        assert_equal(bidtxid1,bidtx2["vin"][0]["txid"])

        # Test coin selection fills amount when TX_LOCKED_MULTISIG outputs not
        # sufficient
        self.nodes[0].generate(19) # request over
        assert(not self.nodes[0].getrequests())
        # new request
        requesttxid = make_request(self.nodes[0])
        self.nodes[0].generate(1)
        time.sleep(4) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        _ = self.nodes[0].getrequestbids(requesttxid)["bids"][0]["txid"] # ensure bid exists


if __name__ == '__main__':
    BiddingTest().main()
