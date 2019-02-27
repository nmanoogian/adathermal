#!/bin/bash
rsync -av --exclude ".*" --exclude ".*/" --exclude "*.pyc" --exclude ".idea" --exclude "venv" --exclude ".git" --delete ./ raspberrypi:adathermal/
# ssh raspberrypi 'sudo systemctl restart thermald'
