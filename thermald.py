#!/usr/bin/python

import argparse
import os
import time
from http import HTTPStatus
from io import BytesIO
from queue import Queue
from threading import Thread
from uuid import uuid4

import requests
import waitress
from PIL import Image
from flask import Flask, request
from flask_cors import CORS

from adapters.tagadapter import TagAdapter
from adathermal import ThermalPrinter

app = Flask(__name__)

CORS(app)

print_queue = Queue()

stop_sentinel = object()


class PrintTask:
    def __init__(self, format_type, body):
        self.format_type = format_type
        self.body = body


@app.route("/", methods=["GET"])
def index():
    return ""


@app.route("/print", methods=["POST"])
def add_print_task():
    format_type = request.json.get("format", "tag")
    if format_type not in ["plain", "tag"]:
        return "Bad format", HTTPStatus.BAD_REQUEST
    body = request.json["body"]
    print_queue.put(PrintTask(format_type, body))
    return "OK"


@app.route("/print-image", methods=["POST"])
def add_image_print_task():
    if 'file' not in request.files:
        return "Missing `file`", HTTPStatus.BAD_REQUEST
    path = "/tmp/{}".format(uuid4())
    request.files['file'].save(path)
    print_queue.put(PrintTask("image-file", path))
    return "OK"


@app.route("/print-image-url", methods=["POST"])
def add_image_print_url_task():
    image_url = request.json.get("url")
    image_data = requests.get(image_url).content
    print_queue.put(PrintTask("image-data", BytesIO(image_data)))
    return "OK"


def create_printer(args):
    if not args.stdout:
        return ThermalPrinter("/dev/serial0", 19200, timeout=5)
    else:
        return ThermalPrinter()


def print_loop(args):
    printer = create_printer(args)
    tag_adapter = TagAdapter(printer)

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
            if task.format_type == "tag":
                tag_adapter.print(task.body)
            elif task.format_type == "image-file":
                printer.print_image(Image.open(task.body))
                os.remove(task.body)
            elif task.format_type == "image-data":
                printer.print_image(Image.open(task.body))
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
    waitress.serve(app, port=8080)
    print_queue.put(stop_sentinel)


if __name__ == "__main__":
    main()
