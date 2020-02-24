#!/usr/bin/env python3

"""test methods of Challenge class

"""
import logging

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
from test_framework.key import CPubKey
from guardnode.challenge import Challenge, asset_in_block

# args object to pass into Challenge instance for testing
class Args:
    def __init__(self):
        self.rpchost = "127.0.0.1:"+str(rpc_port(0))
        rpc_u, rpc_p = rpc_auth_pair(0)
        self.rpcuser = rpc_u
        self.rpcpass = rpc_p
        self.servicerpchost = "127.0.0.1:"+str(rpc_port(0))
        rpc_u, rpc_p = rpc_auth_pair(0)
        self.servicerpcuser = rpc_u
        self.servicerpcpass = rpc_p

        self.challengehost = ""
        self.uniquebidpubkeys = False
        self.bidpubkey = None
        self.bidlimit = 15
        self.serviceblocktime = 1


class ChallengeTest(BitcoinTestFramework):
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
        self.nodes[0].importprivkey("cTnxkovLhGbp7VRhMhGThYt8WDwviXgaVAD8DjaVa5G5DApwC6tF") # assets location
        self.nodes[0].generate(101)
        self.sync_all()
        genesis = self.nodes[0].getblockhash(0)

        args = Args()
        challenge = Challenge(args)

        # Test check_for_request method
        assert(not challenge.check_for_request()) # return False when no request

        # Make request
        requesttxid = make_request(self.nodes[0])
        self.nodes[0].generate(1)
        assert_equal(len(self.nodes[0].getrequests()),1)

        # Test check_for_request method returns request
        assert_equal(challenge.check_for_request()["genesisBlock"], genesis) # return request

        # Make another request with different genesis
        blockcount = self.nodes[0].getblockcount()
        unspent = self.nodes[0].listunspent(1, 9999999, [], True, "PERMISSION")
        pubkey = self.nodes[0].validateaddress(self.nodes[0].getnewaddress())["pubkey"]
        new_genesis = "e9a934a8ae2587fbe6b661e69115a5b7b9d624d73a248e9b2bce15e7d1cd48eb"
        inputs = {"txid": unspent[0]["txid"], "vout": unspent[0]["vout"]}
        outputs = {"decayConst": 10, "endBlockHeight": blockcount+20, "fee": 1, "genesisBlockHash": new_genesis,
        "startBlockHeight": blockcount+10, "tickets": 10, "startPrice": 5, "value": unspent[0]["amount"], "pubkey": pubkey}
        tx = self.nodes[0].createrawrequesttx(inputs, outputs)
        signedtx = self.nodes[0].signrawtransaction(tx)
        txid = self.nodes[0].sendrawtransaction(signedtx["hex"])
        self.nodes[0].generate(1)
        assert_equal(len(self.nodes[0].getrequests()),2)

        # Check correct request fetched for each genesis
        assert_equal(challenge.check_for_request()["genesisBlock"],genesis)
        challenge.genesis = new_genesis
        challenge.request = challenge.check_for_request()
        assert_equal(challenge.request["genesisBlock"],new_genesis)


        # Test check_for_bid_from_wallet method
        # No bids
        assert_equal(challenge.check_for_bid_from_wallet(),None)

        # make bid with different wallet receive address
        tx = self.nodes[0].listunspent(1, 9999999, [], True, "CBT")[0]
        change = float(tx["amount"]) - 5 - 0.001
        addr = self.nodes[1].getnewaddress() # receive address not in service_ocean wallet
        input = [{"txid":tx["txid"],"vout":tx["vout"]}]
        bidtxraw = self.nodes[0].createrawbidtx(input,{"feePubkey":pubkey,"pubkey":pubkey,
            "value":5,"change":change,"changeAddress":addr,"fee":0.001,"endBlockHeight":blockcount+20,"requestTxid":txid})
        nonwalletbidtx = self.nodes[0].sendrawtransaction(self.nodes[0].signrawtransaction(bidtxraw)["hex"])
        self.nodes[0].generate(0)
        # test un-owned bid returns no bid_txid
        assert_equal(challenge.check_for_bid_from_wallet(),None)


        # Test check_ready_for_bid()
        assert(challenge.check_ready_for_bid()) # no bid made
        # make bid
        tx = self.nodes[0].listunspent(100, 9999999, [], False, "CBT")[0]
        change = float(tx["amount"]) - 5 - 0.001
        addr = self.nodes[0].getnewaddress()
        input = [{"txid":tx["txid"],"vout":tx["vout"]}]
        bidtxraw = self.nodes[0].createrawbidtx(input,{"feePubkey":pubkey,"pubkey":pubkey,
            "value":5,"change":change,"changeAddress":addr,"fee":0.001,"endBlockHeight":blockcount+20,"requestTxid":txid})
        challenge.bid_txid = self.nodes[0].sendrawtransaction(self.nodes[0].signrawtransaction(bidtxraw)["hex"])
        self.nodes[0].generate(1)
        assert(not challenge.check_ready_for_bid()) # bid made
        # all tickets sold
        challenge.request["numTickets"] = 1
        assert(not challenge.check_ready_for_bid())


        # Test check_for_bid_from_wallet method with wallet-owned bid active
        assert_equal(challenge.check_for_bid_from_wallet(),challenge.bid_txid)
        # check key



        # Test gen_feepubkey() and set_key()
        addr = challenge.gen_feepubkey()
        assert_is_hex_string(challenge.client_fee_pubkey) # check exists
        # Check resulting priv key corresponds to fee pub key
        assert_equal(CPubKey(challenge.key.get_pubkey()).hex(),challenge.client_fee_pubkey)


        # Test asset_in_block()
        assets = []
        for issuance in self.nodes[0].listissuances(): # grab each asset
            assets.append(issuance["asset"])
        # test each asset identified in genesis
        for asset in assets:
            assert(asset_in_block(self.nodes[0], hex_str_rev_hex_str(asset), 0))
        self.nodes[0].generate(1)
        # test none found in empty block
        for asset in assets:
            assert_equal(asset_in_block(self.nodes[0], asset, self.nodes[0].getblockcount()), None)
        # test invalid asset argument
        assert_equal(asset_in_block(self.nodes[0], None, 0), None)
        assert_equal(asset_in_block(self.nodes[0], 1234, 0), None)
        assert_equal(asset_in_block(self.nodes[0], 0, 0), None)


        # Test await_challenge()
        block_count = self.nodes[0].getblockcount()
        challenge.last_block_height = block_count
        challenge.request = {"endBlockHeight":block_count+2,"startBlockHeight":block_count+1,"txid":"1234"}
        # Check request not yet started
        assert_equal(challenge.await_challenge(),True)
        # Check Challenge asset check called
        self.nodes[0].generate(1)
        assert_equal(challenge.await_challenge(),True)
        # Check request ended
        self.nodes[0].generate(2)
        assert(not challenge.await_challenge())


        # Test generate_response()
        challenge.bid_txid = txid
        data, headers = challenge.generate_response(txid)
        assert(data)
        assert(headers)
        # Check sig against public key
        pubkey = CPubKey(hex_str_to_bytes(challenge.client_fee_pubkey))
        sig = data[data.find("sig")+7:-2]
        assert(pubkey.verify(hex_str_to_rev_bytes(txid),hex_str_to_bytes(sig)))


if __name__ == '__main__':
    ChallengeTest().main()
