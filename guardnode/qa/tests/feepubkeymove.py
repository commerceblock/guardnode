#!/usr/bin/env python3

"""test bidding functionality

"""

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
from challenge import *

class Args:
    def __init__(self):
        self.rpchost = "127.0.0.1:"+str(rpc_port(0))
        rpc_u, rpc_p = rpc_auth_pair(0)
        self.rpcuser = rpc_u
        self.rpcpass = rpc_p
        self.servicerpchost = "127.0.0.1:"+str(rpc_port(1))
        rpc_u, rpc_p = rpc_auth_pair(1)
        self.servicerpcuser = rpc_u
        self.servicerpcpass = rpc_p

        self.challengehost = ""
        self.uniquebidpubkeys = False
        self.bidpubkey = None
        self.bidlimit = 15
        self.serviceblocktime = 1

class BiddingTest(BitcoinTestFramework):

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

        args = Args()
        challenge = Challenge(args)

        # Test fix for fee pubkey generated by wrong wallet
        serv_addr = self.nodes[1].getnewaddress()
        serv_feepubkey = self.nodes[1].validateaddress(serv_addr)["pubkey"]
        assert(self.nodes[1].dumpprivkey(serv_addr))
        try: self.nodes[0].dumpprivkey(serv_addr)
        except Exception as e: assert("Private key for address" in str(e)) # check priv key not known error message
        # now call set_key_from_feepubkey() with feepubkey secret known by service wallet but not client wallet
        challenge.set_key_from_feepubkey(serv_feepubkey)
        # client wallet should now know priv key
        assert(self.nodes[0].dumpprivkey(serv_addr))


if __name__ == '__main__':
    BiddingTest().main()
