#!/usr/bin/env python3
import logging
from decimal import *

DEFAULT_BID_FEE = Decimal("0.0001")

def connect(host, user, pw):
    return authproxy.AuthServiceProxy("http://%s:%s@%s"% (user, pw, host))

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

    # Select coins to fund bid transaction as:
    # Until desired sum is reached:
    #   1. Include TX_LOCKED_MULTISIG outputs of any size
    #   2. Include single regular output of size large enough to cover (input sum - result of 1.)
    #   3. Include all other outputs
    def coin_selection(self, auctionprice):
        list_unspent = self.service_ocean.listunspent(1, 9999999, [], True, "CBT")
        input_sum = Decimal(0.0)
        bid_inputs = []
        # First try to use previous TX_LOCKED_MULTISIG outputs with valid locktime
        for unspent in list_unspent:
            if not unspent["solvable"] and self.check_locktime(unspent["txid"]):
                bid_inputs.append({"txid":unspent["txid"],"vout":unspent["vout"]})
                input_sum += unspent["amount"]
                if input_sum >= auctionprice + self.bid_fee:
                    break
        # Next try to find a single input to cover the remaining amount
        if input_sum < auctionprice + self.bid_fee:
            for unspent in list_unspent:
                # check amount, not already in list and locktime
                if unspent["amount"] >= auctionprice + self.bid_fee - input_sum \
                and next((False for item in bid_inputs if item["txid"] == unspent["txid"]), True) \
                and self.check_locktime(unspent["txid"]):
                    bid_inputs.append({"txid":unspent["txid"],"vout":unspent["vout"]})
                    input_sum += unspent["amount"]
                    break
        # Otherwise build sum from whichever utxos are available
        if input_sum < auctionprice + self.bid_fee:
            for unspent in list_unspent:
                if next((False for item in bid_inputs if item["txid"] == unspent["txid"]), True) \
                and self.check_locktime(unspent["txid"]):
                    bid_inputs.append({"txid":unspent["txid"],"vout":unspent["vout"]})
                    input_sum += unspent["amount"]
                    if input_sum >= auctionprice + self.bid_fee:
                        break
        if input_sum < auctionprice + self.bid_fee:
            self.logger.warn("Not enough CBT in wallet to match the auction price {}".format(auctionprice))
            return False, False
        return bid_inputs, input_sum

    # construct, sign and send bid transaction
    def do_request_bid(self, request, client_fee_pubkey):
        if request["startBlockHeight"] <= self.service_ocean.getblockcount():
            self.logger.warn("Too late to bid for request. Service already started")
        elif request["auctionPrice"] > self.bid_limit:
            self.logger.warn("Auction price {} too high for guardnode bid limit {}".format(request["auctionPrice"], self.bid_limit))
        else:
            # find inputs
            bid_inputs, input_sum = self.coin_selection(request["auctionPrice"])
            if not bid_inputs:
                return
            # find outputs
            bid_outputs = {}
            bid_outputs["endBlockHeight"] = request["endBlockHeight"]
            bid_outputs["requestTxid"] = request["txid"]
            bid_outputs["pubkey"] = self.service_ocean.validateaddress(self.service_ocean.getnewaddress())["pubkey"]
            bid_outputs["feePubkey"] = client_fee_pubkey
            bid_outputs["value"] = request["auctionPrice"]
            bid_outputs["change"] = Decimal(input_sum - request["auctionPrice"] - self.bid_fee)
            bid_outputs["changeAddress"] = self.service_ocean.getnewaddress()
            bid_outputs["fee"] = self.bid_fee

            # Make, sign and send transaciton
            raw_bid_tx = self.service_ocean.createrawbidtx(bid_inputs, bid_outputs)
            signed_raw_bid_tx = self.service_ocean.signrawtransaction(raw_bid_tx)
            if signed_raw_bid_tx["complete"] == False:
                self.logger.info("Signing error tx: {}".format(signed_raw_bid_tx["errors"][0]))
            # Import address so TX_LOCKED_MULTISIG output can be spent from
            address = self.service_ocean.decoderawtransaction(signed_raw_bid_tx['hex'])["vout"][0]["scriptPubKey"]["hex"]
            self.service_ocean.importaddress(address)

            bid_txid = self.service_ocean.sendrawtransaction(signed_raw_bid_tx["hex"])
            self.logger.info("Bid {} submitted".format(bid_txid))
            return bid_txid
