#!/usr/bin/env python3
from time import sleep
from argparse import ArgumentParser
from .challenge import Challenge

# This prefix corresponds to the Ocean Custom params
# prefix. Replace with the argumetn below accordingly
ADDRESS_PREFIX_DEFAULT = 235

# Default coordinator host address
COORDINATOR_DEFAULT = "http://coordinator:3333/challengeproof"

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--rpcconnect', required=False, default="127.0.0.1",type=str, help="Client RPC host")
    parser.add_argument('--rpcport', required=False, default="5555", type=str, help="Client RPC port")
    parser.add_argument('--rpcuser', required=False, default="", type=str, help="Client RPC username")
    parser.add_argument('--rpcpassword', required=False, default="", type=str, help="Client RPC password")

    parser.add_argument('--bidtxid', required=True, type=str, help="Guardnode winning bid txid")
    parser.add_argument('--pubkey', required=True, type=str, help="Guardnode public key")

    parser.add_argument('--coordinator', required=False, type=str, default=COORDINATOR_DEFAULT, help="Coordinator host address")
    parser.add_argument('--challengeasset', required=True, type=str, help="Challenge asset hash")

    parser.add_argument('--addressprefix', required=False, type=int, default=235, help="Chain P2PKH address prefix")

    return parser.parse_args()

def main():
    args = parse_args()

    # spawn challenge handling in new thread
    challenge = Challenge(args)
    challenge.start()

    try:
        while 1:
            sleep(300)

    except KeyboardInterrupt:
        challenge.stop()

if __name__ == "__main__":
    main()
