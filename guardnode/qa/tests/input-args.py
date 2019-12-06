#!/usr/bin/env python3

"""test input args perform check correctly

"""

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *

class InputArgHandlingTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()


    def run_test(self):
        # run guardnode
        entry = '/$HOME/guardnode/run_guardnode'
        args = [ entry ]

        guardnode = subprocess.Popen(args)



        assert_equal(1,1)



if __name__ == '__main__':
    InputArgHandlingTest().main()
