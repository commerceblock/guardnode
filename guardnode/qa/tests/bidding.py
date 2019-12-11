#!/usr/bin/env python3

"""test input args perform check correctly

"""
import subprocess


from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *

WAIT_FOR_ERROR = 0.5 # sleep while guardnode errors
WAIT_FOR_WORK = 2 # sleep while guardnode processes

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
        start_guardnode(self.options.tmpdir,["--bidpubkey"])
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'expected one argument'))
        start_guardnode(self.options.tmpdir,["--bidpubkey","12345"])
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'Error: Odd-length string'))

        # Test err on no requests
        start_guardnode(self.options.tmpdir)
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'No active requests for genesis: '+genesis))

        self.nodes[0].generate(1) # mine request tx
        assert_equal(len(self.nodes[0].getrequests()),1)
        bidaddr = self.nodes[0].getnewaddress()
        bidpubkey = self.nodes[0].validateaddress(bidaddr)["pubkey"]
        guardnode = start_guardnode(self.options.tmpdir,["--bidpubkey",bidpubkey])

        # Check found request
        time.sleep(WAIT_FOR_WORK)
        assert(GN_log_contains(self.options.tmpdir,'Found request: '))  # found request log entry
        assert(GN_log_contains(self.options.tmpdir,requesttxid))        # with txid

        # Test bid placed
        time.sleep(WAIT_FOR_WORK) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        # check bid exists in network and GN logs
        bidtxid1 = self.nodes[0].getrequestbids(requesttxid)["bids"][0]["txid"]
        assert(GN_log_contains(self.options.tmpdir,"Bid "+bidtxid1+" submitted"))

        # Test next bid uses TX_LOCKED_MULTISIG output => uses previous bids utxo
        self.nodes[0].generate(19) # request over
        assert(not self.nodes[0].getrequests())
        requesttxid = make_request(self.nodes[0],4) # new request with price 4 to ensure TX_LOCKED_MULTISIG output is used
        self.nodes[0].generate(1)
        time.sleep(WAIT_FOR_WORK) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        bidtxid2 = self.nodes[0].getrequestbids(requesttxid)["bids"][0]["txid"]
        assert(GN_log_contains(self.options.tmpdir,"Bid "+bidtxid2+" submitted")) # check GN logs
        # check bid2 input is bid1 output
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
        time.sleep(WAIT_FOR_WORK) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        bidtxid3 = self.nodes[0].getrequestbids(requesttxid)["bids"][0]["txid"] # ensure bid exists
        assert(GN_log_contains(self.options.tmpdir,"Bid "+bidtxid3+" submitted")) # check GN logs

if __name__ == '__main__':
    BiddingTest().main()
