#!/usr/bin/env python3

"""test bidding functionality

"""

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
from guardnode.bid import *

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

        bid_handler = BidHandler(self.nodes[0],15)
        bid_handler.logger.disabled = True # supress output so warnings dont cause test to
                                    # fail when stderr output is expected behaviour

        # Test check_locktime
        blockcount = self.nodes[0].getblockcount()
        txid = self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(),5,"","",True,"CBT")
        assert(bid_handler.check_locktime(txid,blockcount))
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
        assert(not bid_handler.check_locktime(bidtxid,blockcount)) # Check invalid locktime
        self.nodes[0].generate(1)
        blockcount += 1
        assert(bid_handler.check_locktime(bidtxid,blockcount)) # Check valid locktime


        # Test coin_selection()
        # check no available outputs
        bid_handler.service_ocean = self.nodes[1] # node has no spendable outputs
        bid_inputs, input_sum = bid_handler.coin_selection(1)
        assert(not bid_inputs)
        assert(not input_sum)
        # check full amount reached when no single utxo covers full amount
        for i in range(5):
            self.nodes[0].sendtoaddress(self.nodes[1].getnewaddress(),0.4,"","",True,"CBT")
        self.nodes[0].generate(1)
        bid_inputs, _ = bid_handler.coin_selection(Decimal(1.9))
        assert_equal(len(bid_inputs),5)
        bid_handler.service_ocean = self.nodes[0] # node with plenty of UTXOs
        bid_inputs,_ = bid_handler.coin_selection(10)
        assert_equal(len(bid_inputs),1) # Should have found single input to cover auctionprice (10)
        # Import address so TX_LOCKED_MULTISIG output can be spent from
        address = bidtx["vout"][0]["scriptPubKey"]["hex"]
        self.nodes[0].importaddress(address)
        bid_inputs,input_sum = bid_handler.coin_selection(Decimal(1.9))
        assert_equal(bid_inputs[0]["txid"],bidtxid) # should use bidtx TX_LOCKED_MULTISIG output
        assert_equal('%.3f'%input_sum,'%.3f'%bidtx["vout"][bid_inputs[0]["vout"]]["value"]) # Check amount
        bid_inputs,input_sum = bid_handler.coin_selection(209993)
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
        assert_equal(bid_handler.do_request_bid(request,pubkey),None)
        request["startBlockHeight"] = blockcount+10
        # Test auction price too high
        request["auctionPrice"] = 16
        assert_equal(bid_handler.do_request_bid(request,pubkey),None)
        request["auctionPrice"] = 5
        # Test bid placed
        bidtxid = bid_handler.do_request_bid(request,pubkey)
        assert_is_hex_string(bidtxid)
        self.nodes[0].generate(1)
        assert_equal(bidtxid,self.nodes[0].getrequestbids(self.nodes[0].getrequests()[0]["txid"])["bids"][0]["txid"])


        # Test estimate_fee()
        unspent = self.nodes[0].listunspent()
        inputs = []
        outputs = {}
        addr = self.nodes[0].getnewaddress()
        outputs["endBlockHeight"] = request["endBlockHeight"]
        outputs["requestTxid"] = request["txid"]
        outputs["pubkey"] = self.nodes[0].validateaddress(addr)["pubkey"]
        outputs["feePubkey"] = outputs["pubkey"]
        outputs["changeAddress"] = addr
        outputs["fee"] = 0.0001
        outputs["value"] = 0.0001

        # check failure to estimate fee when not enough txs to base estimate on
        newfee = bid_handler.estimate_fee(inputs,True)
        assert(not newfee)

        # Test tx from single standard tx as input
        # get utxo with standard sciptPubKey
        tx = next(tx for tx in unspent if tx["solvable"])
        outputs["change"] = Decimal(format(tx["amount"] - Decimal(outputs["value"] - outputs["fee"]),".8g"))
        inputs.append({"txid":tx["txid"],"vout":tx["vout"]})
        bid_handler.testing = True
        fee = bid_handler.estimate_fee(inputs,True) # identical function as in BidHandler but without estimesmartfee call
        rawbidtx = self.nodes[0].createrawbidtx(inputs,outputs)
        signedrawbidtx = self.nodes[0].signrawtransaction(rawbidtx)
        signedrawbidtx_size = int(len(signedrawbidtx["hex"])/2)+1
        # bring fee into same magnitude as tx size for comparison
        fee = fee*1000*1000 # fee * 1/feeperbyte value * num. bytes in kb
        # allow 2 bytes overestimate per scriptSig
        assert_greater_than(signedrawbidtx_size,fee-2) # fee in  correct range
        assert_greater_than(fee+2,signedrawbidtx_size) # fee in  correct range

        # Test tx from single locked multisig tx as input
        inputs = []
        tx = next(tx for tx in unspent if not tx["solvable"])
        amount = tx["amount"]
        outputs["change"] = Decimal(format(amount - Decimal(outputs["value"] - outputs["fee"]),".8g"))
        inputs.append({"txid":tx["txid"],"vout":tx["vout"]})
        fee = bid_handler.estimate_fee(inputs,True) # identical function as in BidHandler
        rawbidtx = self.nodes[0].createrawbidtx(inputs,outputs)
        signedrawbidtx = self.nodes[0].signrawtransaction(rawbidtx)
        signedrawbidtx_size = int(len(signedrawbidtx["hex"])/2)+1
        # bring fee into same magnitude as tx size for comparison
        fee = fee*1000*1000 # fee * 1/feeperbyte value * num. bytes in kb
        # allow 2 bytes overestimate per scriptSig
        assert_greater_than(signedrawbidtx_size,fee-2) # fee in  correct range
        assert_greater_than(fee+2,signedrawbidtx_size) # fee in  correct range

        # Test with one of each type of input
        tx = next(tx for tx in unspent if tx["solvable"])
        amount += tx["amount"]
        inputs.append({"txid":tx["txid"],"vout":tx["vout"]})
        outputs["change"] = Decimal(format(amount - Decimal(outputs["value"] - outputs["fee"]),".8g"))
        fee = bid_handler.estimate_fee(inputs,True) # identical function as in BidHandler
        rawbidtx = self.nodes[0].createrawbidtx(inputs,outputs)
        signedrawbidtx = self.nodes[0].signrawtransaction(rawbidtx)
        signedrawbidtx_size = int(len(signedrawbidtx["hex"])/2)+1
        # bring fee into same magnitude as tx size for comparison
        fee = fee*1000*1000 # fee * 1/feeperbyte value * num. bytes in kb
        # allow 2 bytes overestimate per scriptSig
        assert_greater_than(signedrawbidtx_size,fee-4) # fee in  correct range
        assert_greater_than(fee+4,signedrawbidtx_size) # fee in  correct range

        # Test with many inputs
        for i in range(5):
            tx = unspent[i]
            amount += tx["amount"]
            inputs.append({"txid":tx["txid"],"vout":tx["vout"]})
        outputs["change"] = Decimal(format(amount - Decimal(outputs["value"] - outputs["fee"]),".8g"))
        fee = bid_handler.estimate_fee(inputs,True) # identical function as in BidHandler
        rawbidtx = self.nodes[0].createrawbidtx(inputs,outputs)
        signedrawbidtx = self.nodes[0].signrawtransaction(rawbidtx)
        signedrawbidtx_size = int(len(signedrawbidtx["hex"])/2)+1
        # bring fee into same magnitude as tx size for comparison
        fee = fee*1000*1000 # fee * 1/feeperbyte value * num. bytes in kb
        # allow 2 bytes overestimate per scriptSig
        assert_greater_than(signedrawbidtx_size,fee-10) # fee in  correct range
        assert_greater_than(fee+10,signedrawbidtx_size) # fee in  correct range

if __name__ == '__main__':
    BiddingTest().main()
