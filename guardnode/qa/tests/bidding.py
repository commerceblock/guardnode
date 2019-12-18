#!/usr/bin/env python3

"""test bidding functionality

"""
import imp
import sys

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
# TODO fix imports - had to force this because guardnode.bid isnt recognised
bid = imp.load_source('bid', 'guardnode/bid.py')
from bid import *

class Args:
    def __init__(self,ocean):
        self.ocean = ocean
        self.bid_fee = Decimal("0.0001")
        self.bid_limit = 15
        self.service_ocean = ocean
        self.logger = logging.getLogger("Bid")
        self.logger.disabled = True # supress output so warnings dont cause test to
                                    # when error is expected behaviour
    def check_locktime(self,txid):
        return BidHandler.check_locktime(self,txid)
    def coin_selection(self, auctionprice):
        return BidHandler.coin_selection(self, auctionprice)

class BiddingTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.setup_clean_chain = True
        self.num_nodes = 2
        self.extra_args = [["-txindex=1 -initialfreecoins=50000000000000", "-policycoins=50000000000000",
    "-permissioncoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-initialfreecoinsdestination=76a914bc835aff853179fa88f2900f9003bb674e17ed4288ac",
    "-challengecoinsdestination=76a91415de997afac9857dc97cdd43803cf1138f3aaef788ac",
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

        args = Args(self.nodes[0]) # dummy args instance

        # Test check_locktime
        txid = self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(),5,"","",True,"CBT")
        assert(BidHandler.check_locktime(args,txid))
        # make bid out of new tx
        tx = self.nodes[0].decoderawtransaction(self.nodes[0].getrawtransaction(txid))
        vout = 0 if tx["vout"][1]["scriptPubKey"]["type"] == "fee" else 1
        value = float(tx["vout"][vout]["value"]) - 2.0 - 0.001
        addr = self.nodes[0].getnewaddress()
        pubkey = self.nodes[0].validateaddress(addr)["pubkey"]
        endBlockHeight = self.nodes[0].getblockcount() + 1
        bidtxraw = self.nodes[0].createrawbidtx([{"txid":txid,"vout":vout}],{"feePubkey":pubkey,"pubkey":pubkey,
            "value":value,"change":2,"changeAddress":addr,"fee":0.001,"endBlockHeight":endBlockHeight,"requestTxid":txid})
        bidtxid = self.nodes[0].sendrawtransaction(self.nodes[0].signrawtransaction(bidtxraw)["hex"])
        bidtx = self.nodes[0].decoderawtransaction(bidtxraw)
        assert_not(BidHandler.check_locktime(args,bidtxid)) # Check invalid locktime
        self.nodes[0].generate(1)
        assert(BidHandler.check_locktime(args,bidtxid)) # Check valid locktime


        # Test coin_selection()
        # check no available outputs
        args.service_ocean = self.nodes[1] # node has no spendable outputs
        bid_inputs, input_sum = BidHandler.coin_selection(args,1)
        assert_not(bid_inputs)
        assert_not(input_sum)
        # check full amount reached when no single utxo covers full amount
        for i in range(5):
            self.nodes[0].sendtoaddress(self.nodes[1].getnewaddress(),0.4,"","",True,"CBT")
        self.nodes[0].generate(1)
        self.sync_all()
        bid_inputs, _ = BidHandler.coin_selection(args,Decimal(1.9))
        assert_equal(len(bid_inputs),5)
        args.service_ocean = self.nodes[0] # node with plenty of UTXOs
        bid_inputs,_ = BidHandler.coin_selection(args,10)
        assert(len(bid_inputs)) # Should have found single input to cover auctionprice (10)
        # Import address so TX_LOCKED_MULTISIG output can be spent from
        address = bidtx["vout"][0]["scriptPubKey"]["hex"]
        self.nodes[0].importaddress(address)
        bid_inputs,input_sum = BidHandler.coin_selection(args,Decimal(1.9))
        assert_equal(bid_inputs[0]["txid"],bidtxid) # should use bidtx TX_LOCKED_MULTISIG output
        assert_equal('%.3f'%input_sum,'%.3f'%bidtx["vout"][bid_inputs[0]["vout"]]["value"])
        bid_inputs,input_sum = BidHandler.coin_selection(args,209993)
        assert_equal(bid_inputs[0]["txid"],bidtxid) # should use bidtx TX_LOCKED_MULTISIG
        assert_greater_than(len(bid_inputs),1)      # and others to fill remaining fee amount
        assert_greater_than(input_sum, 209993)


        # Test do_request_bid() correctly forming bid
        requesttxid = make_request(self.nodes[0])
        self.nodes[0].generate(1)
        request = self.nodes[0].getrequests()[0]
        blockcount = self.nodes[0].getblockcount()
        # Test too late for bid request
        request["startBlockHeight"] = blockcount-1
        assert_equal(BidHandler.do_request_bid(args,request,pubkey),None)
        request["startBlockHeight"] = blockcount+10
        # Test auction price too high
        request2 = request.copy()
        request2["auctionPrice"] = 16
        assert_equal(BidHandler.do_request_bid(args,request2,pubkey),None)
        # Test bid placed
        bidtxid = BidHandler.do_request_bid(args,request,pubkey)
        assert_is_hex_string(bidtxid)
        self.nodes[0].generate(1)
        assert_equal(bidtxid,self.nodes[0].getrequestbids(self.nodes[0].getrequests()[0]["txid"])["bids"][0]["txid"])




if __name__ == '__main__':
    BiddingTest().main()
