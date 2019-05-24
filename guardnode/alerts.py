#!/usr/bin/env python3
import logging
from time import sleep
from .daemon import DaemonThread

def tail_file(file, sleep_time):
    file.seek(0, 2)
    while True:
        where = file.tell()
        line = file.readline()
        if not line:
            sleep(sleep_time)
            file.seek(where)
        else:
            yield line

class Alerts(DaemonThread):
    def __init__(self, args):
        super().__init__()
        self.logger = logging.getLogger("Alerts")
        self.logger.setLevel(logging.INFO)

        self.file = open(args.nodelogfile)
        self.logger.info("Log file read: {}".format(args.nodelogfile))

    def run(self):
        while not self.stop_event.is_set():
            try:
                for line in tail_file(self.file, sleep_time=0.1):
                    if "ERROR" in line:
                        self.logger.error(line.rstrip())
            except Exception as e:
                self.logger.error(e)
                self.error = e
