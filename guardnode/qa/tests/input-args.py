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

        #connect to a local machine for debugging
        #url = "http://bitcoinrpc:DP6DvqZtqXarpeNWyN3LZTFchCCyCUuHwNF7E8pX99x1@%s:%d" % ('127.0.0.1', 18332)
        #proxy = AuthServiceProxy(url)
        #proxy.url = url # store URL on proxy for info
        #self.nodes.append(proxy)

        self.is_network_split=False
        self.sync_all()


    def run_test(self):
        # init node with request
        self.nodes[0].generate(1)
        print(self.nodes[0].getblockchaininfo())
        assert(False)
        return

        # run guardnode
        entry = '/home/tomos/guardnode/run_guardnode'
        args = [ entry ]

        guardnode = start_guardnode()

        guardnode.communicate(None)



        assert_equal(1,1)



if __name__ == '__main__':
    InputArgHandlingTest().main()
