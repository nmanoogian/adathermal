#!/usr/bin/python

import argparse
import time
from http import HTTPStatus
from queue import Queue
from threading import Thread

import waitress
from flask import Flask, request

from adapters.bbcodeadapter import BBCodeAdapter
from adapters.markdownadapter import MarkdownAdapter
from adathermal import ThermalPrinter

app = Flask(__name__)

print_queue = Queue()

stop_sentinel = object()


class PrintTask:
    def __init__(self, format_type, body):
        self.format_type = format_type
        self.body = body


@app.route("/print", methods=["POST"])
def add_print_task():
    format_type = request.json.get("format", "plain")
    if format_type not in ["plain", "bbcode", "markdown"]:
        return "Bad format", HTTPStatus.BAD_REQUEST
    body = request.json["body"]
    print_queue.put(PrintTask(format_type, body))
    return "OK"


def create_printer(args):
    if not args.stdout:
        return ThermalPrinter("/dev/serial0", 19200, timeout=5)
    else:
        return ThermalPrinter()


def print_loop(args):
    printer = create_printer(args)
    bbcode_adapter = BBCodeAdapter(printer)
    markdown_adapter = MarkdownAdapter(printer)

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
            if task.format_type == "bbcode":
                bbcode_adapter.print(task.body)
            elif task.format_type == "markdown":
                markdown_adapter.print(task.body)
            else:
                printer.print(task.body)
            printer.print("\n" * 3)
            print_queue.task_done()
        except IOError as e:
            print("Failed to print task: {}".format(e))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stdout', action='store_true')
    args = parser.parse_args()

    Thread(target=print_loop, args=(args,)).start()
    waitress.serve(app, port=8081)
    print_queue.put(stop_sentinel)


if __name__ == "__main__":
    main()
