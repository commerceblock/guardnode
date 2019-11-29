#!/usr/bin/env python3
import logging
from decimal import *

DEFAULT_BID_FEE = Decimal("0.0001")

class BidHandler():
    def __init__(self, ocean, pubkey, bid_limit, bid_fee):
        self.client_fee_pubkey = pubkey
        self.bid_limit = bid_limit
        self.bid_fee = DEFAULT_BID_FEE if bid_fee is None else Decimal(format(bid_fee, ".8g"))
        self.service_ocean = ocean

        logging.getLogger("BitcoinRPC")
        self.logger = logging.getLogger("Bid")

    def do_request_bid(self, request):
        if request["auctionPrice"] > self.bid_limit:
            self.logger.warn("Auction price {} too high for guardnode bid limit {}".format(request["auctionPrice"], self.bid_limit))
        else:
            # do bidding
            list_unspent = self.service_ocean.listunspent(1, 9999999, [], True, "CBT")
            for unspent in list_unspent:
                if unspent["amount"] >= request["auctionPrice"]:
                    bid_inputs = {}
                    bid_inputs["txid"] = unspent["txid"]
                    bid_inputs["vout"] = unspent["vout"]
                    bid_outputs = {}
                    bid_outputs["endBlockHeight"] = request["endBlockHeight"]
                    bid_outputs["requestTxid"] = request["txid"]
                    bid_outputs["pubkey"] = self.service_ocean.validateaddress(self.service_ocean.getnewaddress())["pubkey"]
                    bid_outputs["feePubkey"] = self.client_fee_pubkey
                    bid_outputs["value"] = request["auctionPrice"]
                    bid_outputs["change"] = unspent["amount"] - request["auctionPrice"] - self.bid_fee
                    bid_outputs["changeAddress"] = self.service_ocean.getnewaddress()
                    bid_outputs["fee"] = self.bid_fee
                    raw_bid_tx = self.service_ocean.createrawbidtx([bid_inputs], bid_outputs)
                    signed_raw_bid_tx = self.service_ocean.signrawtransaction(raw_bid_tx)
                    return self.service_ocean.sendrawtransaction(signed_raw_bid_tx["hex"])
            self.logger.warn("No unspent with enough CBT to match the auction price {}".format(request["auctionPrice"]))
