#!/usr/bin/env python3
from time import sleep
from argparse import ArgumentParser
from .challenge import Challenge

# This prefix corresponds to the Ocean Custom params
# prefix. Replace with the argumetn below accordingly
NODE_ADDR_PREFIX_DEFAULT = 235
NODE_LOG_FILE_DEFAULT = "/home/bitcoin/.bitcoin/ocean_test/"

# Default coordinator host address
CHALLENGE_HOST_DEFAULT = "coordinator:9999"

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--rpcconnect', required=False, default="127.0.0.1",type=str, help="Client RPC host")
    parser.add_argument('--rpcport', required=False, default="5555", type=str, help="Client RPC port")
    parser.add_argument('--rpcuser', required=False, default="", type=str, help="Client RPC username")
    parser.add_argument('--rpcpassword', required=False, default="", type=str, help="Client RPC password")

    parser.add_argument('--nodeaddrprefix', required=False, type=int, default=NODE_ADDR_PREFIX_DEFAULT, help="Node P2PKH address prefix")
    parser.add_argument('--nodelogfile', required=False, type=str, default=NODE_LOG_FILE_DEFAULT, help="Node log file destination")

    parser.add_argument('--bidtxid', required=True, type=str, help="Guardnode winning bid txid")
    parser.add_argument('--bidpubkey', required=True, type=str, help="Guardnode winning bid public key")

    parser.add_argument('--challengehost', required=False, type=str, default=CHALLENGE_HOST_DEFAULT, help="Challenger host address")
    parser.add_argument('--challengeasset', required=True, type=str, help="Challenge asset hash")

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
