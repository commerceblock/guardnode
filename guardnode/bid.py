#!/usr/bin/env python3
import logging
from decimal import *
from .qa.tests.test_framework.authproxy import JSONRPCException

DEFAULT_BID_FEE = Decimal("0.0001")

class BidHandler():
    def __init__(self, ocean, bid_limit):
        self.bid_limit = bid_limit
        self.bid_fee = DEFAULT_BID_FEE
        self.service_ocean = ocean

        logging.getLogger("BitcoinRPC")
        self.logger = logging.getLogger("Bid")

    def check_locktime(self,txid,blockcount):
        tx = self.service_ocean.getrawtransaction(txid, True)
        for outp in tx["vout"]: # check OP_CHECKLOCKTIMEVERIFY in script
            if "OP_CHECKLOCKTIMEVERIFY" in outp["scriptPubKey"]["asm"] \
            and int(outp["scriptPubKey"]["asm"].split(" ")[0]) > blockcount:
                return False
        return True

    # Select coins to fund bid transaction
    # First find TX_LOCKED_MULTISIG outputs then find remaining utxos with the
    # help of fundrawtransaction rpc
    def coin_selection(self, auction_price):
        list_unspent = self.service_ocean.listunspent(1, 9999999, [], True, "CBT")
        input_sum = Decimal(0.0)
        locked_inputs = []
        blockcount = self.service_ocean.getblockcount()

        # First try to use previous TX_LOCKED_MULTISIG outputs with valid locktime
        for unspent in list_unspent:
            if not unspent["solvable"] and self.check_locktime(unspent["txid"],blockcount):
                locked_inputs.append({"txid":unspent["txid"],"vout":unspent["vout"],"locked":True})
                input_sum += unspent["amount"]
                if input_sum >= auction_price + self.bid_fee:
                    return locked_inputs, input_sum

        # find remaining utxos to make up total value of tx using fundrawtransaction
        dummy_tx = self.service_ocean.createrawtransaction([],{self.service_ocean.getnewaddress():Decimal(format(auction_price + self.bid_fee - input_sum,".8g"))})
        try:
            funded_tx_hex = self.service_ocean.fundrawtransaction(dummy_tx)["hex"]
        except Exception as e:
            if "Insufficient funds" in str(e):
                self.logger.warn("Not enough CBT in wallet to match the auction price {}".format(auction_price))
                return False, False
            else:
                raise

        # get inputs chosen by fundrawtransaction
        funded_tx = self.service_ocean.decoderawtransaction(funded_tx_hex)
        bid_inputs = []
        for input in funded_tx["vin"]:
            bid_inputs.append({"txid":input["txid"],"vout":input["vout"],"locked":False})
        for vout in funded_tx["vout"]:
            input_sum += vout["value"]

        return locked_inputs + bid_inputs, input_sum

    # Take signed_raw_bid_tx and return fee value or False if failure to get estimate fee
    def estimate_fee(self, inputs, change = True):
         # get fee-per-1000-bytes expected for inclusion in next 2 blocks
        feeperkb = self.service_ocean.estimatesmartfee(2)["feerate"]
        if feeperkb == -1: # failed to produce estimate
            return False

        # estimate bid tx size
        size = 12
        # add inputs
        for input in inputs:
            # get script size
            script_size = int(len(self.service_ocean.getrawtransaction(input["txid"],True)["vout"][input["vout"]]["scriptPubKey"]["hex"])/2)
            print(script_size)
            if script_size == 25: # p2phk signature
                size+=(41+110)
            elif script_size < 111 and script_size > 106: # TX_LOCKED_MULTISIG signature
                size+=(41+74)
            else:
                size += 150 # safe over-payment for unknown sig size
        # add outputs
        size += (44 + 109) + (44 + 0) # add locked output and fee output
        if change: # if change output exists
            size += (44 + 25) # add change output
        return Decimal(format(feeperkb * (size / 1000), ".8g"))

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

            # Calculate fee
            change = True
            if input_sum == request["auctionPrice"]: # if no change output
                change = False
            fee = self.estimate_fee(bid_inputs,change)
            if fee:
                self.bid_fee = fee

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

            # Make and sign transaction
            raw_bid_tx = self.service_ocean.createrawbidtx(bid_inputs, bid_outputs)
            signed_raw_bid_tx = self.service_ocean.signrawtransaction(raw_bid_tx)
            
            # send bid tx
            bid_txid = self.service_ocean.sendrawtransaction(signed_raw_bid_tx["hex"])

            # Import address so TX_LOCKED_MULTISIG output can be spent from
            address = self.service_ocean.decoderawtransaction(signed_raw_bid_tx['hex'])["vout"][0]["scriptPubKey"]["hex"]
            self.service_ocean.importaddress(address)

            self.logger.info("Bid {} submitted".format(bid_txid))
            return bid_txid
