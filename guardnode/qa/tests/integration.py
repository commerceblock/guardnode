#!/usr/bin/env python3

"""Test full guardnode functionality

    Spawn guardnode instances and check logs for expected behaviour
"""

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *


class IntegrationTest(BitcoinTestFramework):

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
        self.nodes[0].importprivkey("cTnxkovLhGbp7VRhMhGThYt8WDwviXgaVAD8DjaVa5G5DApwC6tF")
        self.nodes[0].generate(101)
        self.sync_all()
        genesis = self.nodes[0].getblockhash(0)

        # start guardnode
        bidaddr = self.nodes[0].getnewaddress()
        bidpubkey = self.nodes[0].validateaddress(bidaddr)["pubkey"]
        guardnode = start_guardnode(self.options.tmpdir,0,["--bidpubkey",bidpubkey])

        # Test err on no requests
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'No active requests for genesis: '+genesis))

        # Make request
        requesttxid = make_request(self.nodes[0])
        self.nodes[0].generate(1)
        assert_equal(len(self.nodes[0].getrequests()),1)
        time.sleep(WAIT_FOR_WORK) # let guardnode loop
        assert(GN_log_contains(self.options.tmpdir,'Found request: '))  # found request log entry
        assert(GN_log_contains(self.options.tmpdir,requesttxid))        # with txid

        # Test bid placed
        time.sleep(WAIT_FOR_WORK) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        # check bid exists in network and GN logs
        bid1 = self.nodes[0].getrequestbids(requesttxid)["bids"][0]
        assert_equal(bid1["feePubKey"],bidpubkey) # correct bidpubkey used
        assert(GN_log_contains(self.options.tmpdir,"Bid "+bid1["txid"]+" submitted"))

        # Test next bid uses TX_LOCKED_MULTISIG output => uses previous bids utxo
        self.nodes[0].generate(19) # request over
        assert(not self.nodes[0].getrequests())
        requesttxid = make_request(self.nodes[0],4) # new request with price 4 to ensure TX_LOCKED_MULTISIG output is used
        self.nodes[0].generate(1)
        time.sleep(WAIT_FOR_WORK) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        bid2 = self.nodes[0].getrequestbids(requesttxid)["bids"][0] # ensure bid exists
        assert_equal(bid2["feePubKey"],bidpubkey) # correct bidpubkey used
        assert(GN_log_contains(self.options.tmpdir,"Bid "+bid2["txid"]+" submitted")) # check GN logs
        # check bid2 input is bid1 output
        bidtx2 = self.nodes[0].decoderawtransaction(self.nodes[0].getrawtransaction(bid2["txid"]))
        assert_equal(len(bidtx2["vin"]),1)
        assert_equal(bid1["txid"],bidtx2["vin"][0]["txid"])

        # Test coin selection fills amount when TX_LOCKED_MULTISIG outputs not
        # sufficient
        self.nodes[0].generate(19) # request over
        assert(not self.nodes[0].getrequests())
        # new request
        requesttxid = make_request(self.nodes[0])
        self.nodes[0].generate(1)
        time.sleep(WAIT_FOR_WORK) # give time for guardnode to make bid
        self.nodes[0].generate(1)
        bid3 = self.nodes[0].getrequestbids(requesttxid)["bids"][0] # ensure bid exists
        assert_equal(bid3["feePubKey"],bidpubkey) # correct bidpubkey used
        assert(GN_log_contains(self.options.tmpdir,"Bid "+bid3["txid"]+" submitted")) # check GN logs

        # Test fresh bidpubkeys used each bid when uniquebidpubkeys flag provided
        stop_guardnode(guardnode)
        guardnode = start_guardnode(self.options.tmpdir,0,["--uniquebidpubkeys"])
        time.sleep(WAIT_FOR_WORK) # allow set up time
        # make 3 bids on seperate requests and store
        bids = []
        for i in range(3):
            self.nodes[0].generate(19) # ensure currenct request over
            assert(not self.nodes[0].getrequests())
            requesttxid = make_request(self.nodes[0],5)
            self.nodes[0].generate(1)
            time.sleep(WAIT_FOR_WORK) # give time for guardnode to make bid
            self.nodes[0].generate(1)
            bids.append(self.nodes[0].getrequestbids(requesttxid)["bids"][0])

        assert(bids[0]["feePubKey"] != bids[1]["feePubKey"])
        assert(bids[0]["feePubKey"] != bids[2]["feePubKey"])
        assert(bids[1]["feePubKey"] != bids[2]["feePubKey"])

        # Test recognition and response to challenge
        self.nodes[0].generate(15) # bring into service period
        self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(),1,"","",True,"CHALLENGE") # send challenge asset tx
        self.nodes[0].generate(1)
        time.sleep(WAIT_FOR_WORK)
        GN_log_print(self.options.tmpdir)
        assert(GN_log_contains(self.options.tmpdir,'Challenge found at height: '+str(self.nodes[0].getblockcount())))
        time.sleep(WAIT_FOR_WORK)
        assert(GN_log_contains(self.options.tmpdir,'Could not connect to coordinator to send response data:'))


if __name__ == '__main__':
    IntegrationTest().main()
