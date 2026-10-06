#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11 or newer is required"'
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if [ ! -f .venv/.18w-ready ]; then
    .venv/bin/python -m pip install -r requirements.txt
    touch .venv/.18w-ready
fi
exec .venv/bin/python run.py
