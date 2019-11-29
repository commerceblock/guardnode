#!/usr/bin/env python3
import logging
import traceback
from time import sleep
from argparse import ArgumentParser
from .challenge import Challenge
from .alerts import Alerts

# Default debug log file location for ocean nodes in linux machines
NODE_LOG_FILE_DEFAULT = "/home/bitcoin/.bitcoin/ocean_test/debug.log"

# Default coordinator host address
CHALLENGE_HOST_DEFAULT = "http://coordinator:9999"

# Default service block time - can be overriden for testing
SERVICE_BLOCK_TIME_DEFAULT = 60

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--rpchost', required=False, default="127.0.0.1:5555",type=str, help="Client RPC host")
    parser.add_argument('--rpcuser', required=False, default="", type=str, help="Client RPC username")
    parser.add_argument('--rpcpass', required=False, default="", type=str, help="Client RPC password")

    parser.add_argument('--servicerpchost', required=False, default="127.0.0.1:6666",type=str, help="Service RPC host")
    parser.add_argument('--servicerpcuser', required=False, default="", type=str, help="Service RPC username")
    parser.add_argument('--servicerpcpass', required=False, default="", type=str, help="Service RPC password")
    parser.add_argument('--serviceblocktime', required=False, default=SERVICE_BLOCK_TIME_DEFAULT, type=int, help="Service block time")

    parser.add_argument('--nodelogfile', required=False, type=str, default=NODE_LOG_FILE_DEFAULT, help="Node log file destination")

    parser.add_argument('--bidpubkey', required=False, type=str, help="Guardnode winning bid public key")
    parser.add_argument('--bidlimit', required=False, type=float, default="0.0", help="Guardnode upper bid limit")
    parser.add_argument('--bidfee', required=False, type=float, default=None, help="Guardnode bid fee")

    parser.add_argument('--challengehost', required=False, type=str, default=CHALLENGE_HOST_DEFAULT, help="Challenger host address")

    return parser.parse_args()

def run_guardnode(args):
    # spawn challenge handling in new thread
    challenge = Challenge(args)
    challenge.start()

    # spawn alert handling in new thread
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
