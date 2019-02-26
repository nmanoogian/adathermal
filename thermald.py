#!/usr/bin/python

import argparse
import re
import time
from queue import Queue
from threading import Thread

import waitress
from flask import Flask, request

from adathermal import ThermalPrinter

app = Flask(__name__)

print_queue = Queue()

stop_sentinel = object()


@app.route("/print", methods=["POST"])
def add_print_task():
    body = request.json["body"]
    print_queue.put(body)
    return "OK"


def create_printer(args):
    if not args.stdout:
        return ThermalPrinter("/dev/serial0", 19200, timeout=5)
    else:
        return ThermalPrinter()


def print_loop(args):
    printer = create_printer(args)

    while True:
        try:
            # Attempt a write to verify that printer is connected
            printer.set_size('S')
        except IOError as e:
            print("Failed to connect to printer: {}".format(e))
            time.sleep(1)
            printer = create_printer(args)
            continue

        try:
            task = print_queue.get()
            if task is stop_sentinel:
                break
            for line in task.splitlines():
                header_match = re.match(r"(?P<hashes>#{1,2})\s*(?P<text>.*)", line)
                bold_match = re.match(r"\*(?P<text>.*)\*$", line)
                if header_match is not None:
                    if len(header_match.group("hashes")) == 1:
                        printer.set_size("L")
                    else:
                        printer.set_size("M")
                    printer.println(header_match.group("text").encode("ascii", "ignore"))
                    printer.set_size("S")
                elif bold_match is not None:
                    printer.bold_on()
                    printer.println(bold_match.group("text").encode("ascii", "ignore"))
                    printer.bold_off()
                else:
                    printer.println(line.encode("ascii", "ignore"))
            print_queue.task_done()
        except IOError as e:
            print("Failed to print task: {}".format(e))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stdout', action='store_true')
    args = parser.parse_args()

    Thread(target=print_loop, args=(args,)).start()
    waitress.serve(app)
    print_queue.put(stop_sentinel)


if __name__ == "__main__":
    main()
