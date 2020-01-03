#!/usr/bin/env python3

"""test bidding functionality

"""

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
from guardnode.bid import *


class Args:
    def __init__(self,ocean):
        self.ocean = ocean
        self.bid_fee = Decimal("0.0001")
        self.bid_limit = 15
        self.service_ocean = ocean
        self.logger = logging.getLogger("Bid")
        self.trigger_estimate_fee = False
        self.logger.disabled = True # supress output so warnings dont cause test to
                                    # when error is expected behaviour
    def check_locktime(self,txid,blockcount):
        return BidHandler.check_locktime(self,txid,blockcount)
    def coin_selection(self, auctionprice):
        return BidHandler.coin_selection(self, auctionprice)
    def estimate_fee(self,signed_raw_tx):
        if self.trigger_estimate_fee:
            # same calculation as in actual function
            feeperkb = 0.01
            size = int(len(signed_raw_tx["hex"]) / 2) + 1
            return Decimal(format(feeperkb * (size / 1000), ".8g"))
        return False

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
        blockcount = self.nodes[0].getblockcount()
        txid = self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(),5,"","",True,"CBT")
        assert(BidHandler.check_locktime(args,txid,blockcount))
        # make bid out of new tx
        tx = self.nodes[0].decoderawtransaction(self.nodes[0].getrawtransaction(txid))
        vout = 0 if tx["vout"][1]["scriptPubKey"]["type"] == "fee" else 1
        value = float(tx["vout"][vout]["value"]) - 2.0 - 0.001
        addr = self.nodes[0].getnewaddress()
        pubkey = self.nodes[0].validateaddress(addr)["pubkey"]
        endBlockHeight = blockcount + 1
        bidtxraw = self.nodes[0].createrawbidtx([{"txid":txid,"vout":vout}],{"feePubkey":pubkey,"pubkey":pubkey,
            "value":value,"change":2,"changeAddress":addr,"fee":0.001,"endBlockHeight":endBlockHeight,"requestTxid":txid})
        bidtxid = self.nodes[0].sendrawtransaction(self.nodes[0].signrawtransaction(bidtxraw)["hex"])
        bidtx = self.nodes[0].decoderawtransaction(bidtxraw)
        assert(not BidHandler.check_locktime(args,bidtxid,blockcount)) # Check invalid locktime
        self.nodes[0].generate(1)
        blockcount += 1
        assert(BidHandler.check_locktime(args,bidtxid,blockcount)) # Check valid locktime


        # Test coin_selection()
        # check no available outputs
        args.service_ocean = self.nodes[1] # node has no spendable outputs
        bid_inputs, input_sum = BidHandler.coin_selection(args,1)
        assert(not bid_inputs)
        assert(not input_sum)
        # check full amount reached when no single utxo covers full amount
        for i in range(5):
            self.nodes[0].sendtoaddress(self.nodes[1].getnewaddress(),0.4,"","",True,"CBT")
        self.nodes[0].generate(1)
        bid_inputs, _ = BidHandler.coin_selection(args,Decimal(1.9))
        assert_equal(len(bid_inputs),5)
        args.service_ocean = self.nodes[0] # node with plenty of UTXOs
        bid_inputs,_ = BidHandler.coin_selection(args,10)
        assert_equal(len(bid_inputs),1) # Should have found single input to cover auctionprice (10)
        # Import address so TX_LOCKED_MULTISIG output can be spent from
        address = bidtx["vout"][0]["scriptPubKey"]["hex"]
        self.nodes[0].importaddress(address)
        bid_inputs,input_sum = BidHandler.coin_selection(args,Decimal(1.9))
        assert_equal(bid_inputs[0]["txid"],bidtxid) # should use bidtx TX_LOCKED_MULTISIG output
        assert_equal('%.3f'%input_sum,'%.3f'%bidtx["vout"][bid_inputs[0]["vout"]]["value"]) # Check amount
        bid_inputs,input_sum = BidHandler.coin_selection(args,209993)
        assert_equal(bid_inputs[0]["txid"],bidtxid) # should use bidtx's TX_LOCKED_MULTISIG
        assert_greater_than(len(bid_inputs),1)      # and others to fill remaining fee amount
        assert_greater_than(input_sum, 209993)


        # Test do_request_bid() correctly forming bid
        make_request(self.nodes[0])
        self.nodes[0].generate(1)
        request = self.nodes[0].getrequests()[0]
        blockcount = self.nodes[0].getblockcount()
        # Test too late for bid request
        request["startBlockHeight"] = blockcount-1
        assert_equal(BidHandler.do_request_bid(args,request,pubkey),None)
        request["startBlockHeight"] = blockcount+10
        # Test auction price too high
        request["auctionPrice"] = 16
        assert_equal(BidHandler.do_request_bid(args,request,pubkey),None)
        request["auctionPrice"] = 5
        # Test bid placed
        bidtxid = BidHandler.do_request_bid(args,request,pubkey)
        assert_is_hex_string(bidtxid)
        self.nodes[0].generate(1)
        assert_equal(bidtxid,self.nodes[0].getrequestbids(self.nodes[0].getrequests()[0]["txid"])["bids"][0]["txid"])
        # Test estimatefee causes new bid with new fee
        args.trigger_estimate_fee = True
        bidtxid = BidHandler.do_request_bid(args,request,pubkey)
        assert_is_hex_string(bidtxid)
        self.nodes[0].generate(1)
        assert_equal(len(self.nodes[0].getrequestbids(self.nodes[0].getrequests()[0]["txid"])["bids"]),2)
        bidtx = self.nodes[0].decoderawtransaction(self.nodes[0].getrawtransaction(bidtxid))
        vout = next(item["n"] for item in bidtx["vout"] if item["scriptPubKey"]["type"] == "fee")
        assert_greater_than(bidtx["vout"][vout]["value"],0.005) # fee in  correct range
        assert_greater_than(0.015,bidtx["vout"][vout]["value"]) # fee in  correct range


        # Test fee estimation
        # check failure to estimate fee when not enough txs to base estimate on
        signed_raw_tx = {'hex': '020000000001c1380cd5ab57e656d6c6825139538ab12f5fac71eb8336c3aacc673bb3b9c6cf000000006a4730440220737bd98b89d7c97fa0027d3364a79e71efdf48541c94e8d6cfa3abf7dec71412022060d47ef1f16b6920c8e65cd4bd0d5d58ebb0a55113f09689d05133062510b474012103025ecf586d4284e720ba2994d8d218cc38b7b86a0549fd341ccb399f16f2ca7afeffffff03018af3413eecabe8ace374f6c25efd07c46b72ba9edf77f604d22a023f7bc956a101000000001dcd6500006d0179b175512103bc966cc8a79361de0f864c77cfef7a138942c1d9d645cd069b658c43e08e31952102595a910d6287f79583fcfe50cc15be43b825b596d496ef42d5f2c519707405fc21028767253aedb195fa6874d79c1cc1da4f0807b9f219fc8ad558724d01cc11160453ae018af3413eecabe8ace374f6c25efd07c46b72ba9edf77f604d22a023f7bc956a1010000131953bcc3f0001976a914447b751cb5ebd9162de946f67bff88c81e8cc70b88ac018af3413eecabe8ace374f6c25efd07c46b72ba9edf77f604d22a023f7bc956a1010000000000002710000066000000', 'complete': True}
        newfee = BidHandler.estimate_fee(args,signed_raw_tx)
        assert(not newfee)

if __name__ == '__main__':
    BiddingTest().main()
