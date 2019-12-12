#!/usr/bin/env python3
import logging
from decimal import *

DEFAULT_BID_FEE = Decimal("0.0001")

class BidHandler():
    def __init__(self, ocean, bid_limit, bid_fee):
        self.bid_limit = bid_limit
        self.bid_fee = DEFAULT_BID_FEE if bid_fee is None else Decimal(format(bid_fee, ".8g"))
        self.service_ocean = ocean

        logging.getLogger("BitcoinRPC")
        self.logger = logging.getLogger("Bid")

    def check_locktime(self, txid):
        tx = self.service_ocean.decoderawtransaction(self.service_ocean.getrawtransaction(txid))
        blockcount = self.service_ocean.getblockcount()
        for outp in tx["vout"]: # check OP_CHECKLOCKTIMEVERIFY in script
            if "OP_CHECKLOCKTIMEVERIFY" in outp["scriptPubKey"]["asm"] \
            and int(outp["scriptPubKey"]["asm"].split(" ")[0]) > blockcount:
                return False
        return True

    def do_request_bid(self, request, client_fee_pubkey):
        if request["startBlockHeight"] <= self.service_ocean.getblockcount():
            self.logger.warn("Too late to bid for request. Service already started")
        elif request["auctionPrice"] > self.bid_limit:
            self.logger.warn("Auction price {} too high for guardnode bid limit {}".format(request["auctionPrice"], self.bid_limit))
        else:
            # do bidding
            # find inputs
            list_unspent = self.service_ocean.listunspent(1, 9999999, [], True, "CBT")
            input_sum = 0
            bid_inputs = []
            # First try to use previous TX_LOCKED_MULTISIG outputs with valid locktime
            for unspent in list_unspent:
                if not unspent["solvable"] and self.check_locktime(unspent["txid"]):
                    bid_inputs.append({"txid":unspent["txid"],"vout":unspent["vout"]})
                    input_sum += unspent["amount"]
                    if input_sum >= request["auctionPrice"] + self.bid_fee:
                        break
            # Next try to find a single input to cover the remaining amount
            if input_sum < request["auctionPrice"] + self.bid_fee:
                for unspent in list_unspent:
                    # check amount, not already in list and locktime
                    if unspent["amount"] >= request["auctionPrice"] - input_sum \
                    and next((False for item in bid_inputs if item["txid"] == unspent["txid"]), True) \
                    and self.check_locktime(unspent["txid"]):
                        bid_inputs.append({"txid":unspent["txid"],"vout":unspent["vout"]})
                        input_sum += unspent["amount"]
                        break
            # Otherwise build sum from whichever utxos are available
            if input_sum < request["auctionPrice"] + self.bid_fee:
                for unspent in list_unspent:
                    if next((False for item in bid_inputs if item["txid"] == unspent["txid"]), True) \
                    and self.check_locktime(unspent["txid"]):
                        bid_inputs.append({"txid":unspent["txid"],"vout":unspent["vout"]})
                        input_sum += unspent["amount"]
                        if input_sum >= request["auctionPrice"] + self.bid_fee:
                            break
            if input_sum < request["auctionPrice"] + self.bid_fee:
                self.logger.warn("Not enough CBT in wallet to match the auction price {}".format(request["auctionPrice"]))
                return
            bid_outputs = {}
            bid_outputs["endBlockHeight"] = request["endBlockHeight"]
            bid_outputs["requestTxid"] = request["txid"]
            bid_outputs["pubkey"] = self.service_ocean.validateaddress(self.service_ocean.getnewaddress())["pubkey"]
            bid_outputs["feePubkey"] = client_fee_pubkey
            bid_outputs["value"] = request["auctionPrice"]
            bid_outputs["change"] = input_sum - request["auctionPrice"] - self.bid_fee
            bid_outputs["changeAddress"] = self.service_ocean.getnewaddress()
            bid_outputs["fee"] = self.bid_fee
            raw_bid_tx = self.service_ocean.createrawbidtx(bid_inputs, bid_outputs)
            signed_raw_bid_tx = self.service_ocean.signrawtransaction(raw_bid_tx)
            if signed_raw_bid_tx["complete"] == False:
                self.logger.info("Signing error tx: {}".format(signed_raw_bid_tx["errors"][0]))

            # Import address so TX_LOCKED_MULTISIG output can be spent from
            address = self.service_ocean.decoderawtransaction(signed_raw_bid_tx['hex'])["vout"][0]["scriptPubKey"]["hex"]
            self.service_ocean.importaddress(address)

            return self.service_ocean.sendrawtransaction(signed_raw_bid_tx["hex"])
