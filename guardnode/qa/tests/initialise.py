#!/usr/bin/env python3

"""test initialisation - getting sidechain info and checking input args

"""

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *

from guardnode.challenge import get_challenge_asset

class InitialisationTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [["-txindex=1 -initialfreecoins=50000000000000", "-policycoins=50000000000000",
    "-permissioncoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-initialfreecoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-challengecoinsdestination=76a91415de997afac9857dc97cdd43803cf1138f3aaef788ac",
    "-debug=1"],["-txindex"]]

    def setup_network(self, split=False):
        self.nodes = start_nodes(self.num_nodes, self.options.tmpdir, self.extra_args)
        self.is_network_split=False

    def run_test(self):
        # init nodes[0]
        self.nodes[0].importprivkey("cTnxkovLhGbp7VRhMhGThYt8WDwviXgaVAD8DjaVa5G5DApwC6tF")
        self.nodes[0].generate(101)
        genesis = self.nodes[0].getblockhash(0)

        # Check challenge asset found
        assert_is_hex_string(get_challenge_asset(self.nodes[0]))

        # Test no challenge asset found
        assert_not(get_challenge_asset(self.nodes[1])) # nodes[1] has no  challenge asset
        start_guardnode(self.options.tmpdir, 1) # start guardnode connected to nodes[1]
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'No Challenge asset found in client chain'))

        # The following tests are for initialisation of genfeepubkey functionality only.
        # Testing for which bidpubkey are used for each bid are in integration.py.
        # Test activation of genfeepubkey flag
        guardnode = start_guardnode(self.options.tmpdir,0,["--uniquebidpubkeys"])
        time.sleep(WAIT_FOR_WORK) # allow set up time
        stop_guardnode(guardnode)
        assert(GN_log_contains(self.options.tmpdir,"Fee pubkey will be freshly generated each bid"))

        # New pubkey generated if no bidpukkey argument given
        guardnode = start_guardnode(self.options.tmpdir,0)
        time.sleep(WAIT_FOR_WORK) # allow set up time
        stop_guardnode(guardnode)
        assert(GN_log_contains(self.options.tmpdir,"Fee address:"))

        # given pubkey used if bidpubkey argument given
        bidaddr = self.nodes[0].getnewaddress()
        bidpubkey = self.nodes[0].validateaddress(bidaddr)["pubkey"]
        guardnode = start_guardnode(self.options.tmpdir,0,["--bidpubkey",bidpubkey])
        time.sleep(WAIT_FOR_WORK) # allow set up time
        stop_guardnode(guardnode)
        assert(GN_log_contains(self.options.tmpdir,"Fee address: "+str(bidaddr)+" and pubkey: "+str(bidpubkey)))

        # Test error for bad bidpubkey
        start_guardnode(self.options.tmpdir,0,["--bidpubkey"])
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'expected one argument'))
        start_guardnode(self.options.tmpdir,0,["--bidpubkey","12345"])
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'Error: Odd-length string'))

        # Test unowned bidpubkey given
        start_guardnode(self.options.tmpdir,0,["--bidpubkey","023785ce7924ff8a928d2e747194ca970ba21576f8d4de96662c58d456eda7cf65"])
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'is missing from the wallet'))



if __name__ == '__main__':
    InitialisationTest().main()
