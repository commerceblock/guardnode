#!/usr/bin/env python3
import logging
import traceback
from time import sleep
from argparse import ArgumentParser
from .challenge import Challenge
from .alerts import Alerts

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

def run_guardnode(args):
    # spawn challenge handling in new thread
    challenge = Challenge(args)
    challenge.start()

    # spawn allerts handling in new thread
    alerts = Alerts(args)
    alerts.start()

    return (challenge, alerts)

def main():
    args = parse_args()
    logging.basicConfig(
        format='%(asctime)s %(name)s:%(levelname)s:%(process)d: %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger("Guardnode")

    challenge_handler = None
    alerts_handler = None
    try:
        (challenge_handler, alerts_handler) = run_guardnode(args)
        while True:
            if challenge_handler.error:
                raise challenge_handler.error
            if alerts_handler.error:
                raise alerts_handler.error
            sleep(0.01)

    except KeyboardInterrupt:
        logger.error("KeyboardInterrupt")
    except Exception as e:
        logger.error(traceback.format_exc())
    finally:
        if challenge_handler:
            challenge_handler.stop()
        if alerts_handler:
            alerts_handler.stop()

if __name__ == "__main__":
    main()
