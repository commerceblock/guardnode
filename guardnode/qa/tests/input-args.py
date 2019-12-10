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

    def setup_network(self, split=False):
        self.nodes = start_nodes(self.num_nodes, self.options.tmpdir)
        self.is_network_split=False
        self.sync_all()


    def run_test(self):
        # init node 
        self.nodes[0].generate(1)
        print(self.nodes[0].getblockchaininfo())
        assert(False)
        return

        guardnode = start_guardnode()



if __name__ == '__main__':
    InputArgHandlingTest().main()
