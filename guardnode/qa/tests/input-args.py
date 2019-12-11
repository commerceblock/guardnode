#!/usr/bin/env python3

"""test input args perform check correctly

"""
import subprocess

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *

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
        genesis = self.nodes[0].getblockhash(0)

        # Test error for bad bidpubkey
        start_guardnode(self.options.tmpdir,["--bidpubkey"])
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'expected one argument'))
        start_guardnode(self.options.tmpdir,["--bidpubkey","12345"])
        time.sleep(WAIT_FOR_ERROR)
        assert(GN_log_contains(self.options.tmpdir,'Error: Odd-length string'))

        # TODO: tests for all input arg checks
        # give bidpubkey for which wallet own

if __name__ == '__main__':
    InputArgHandlingTest().main()
