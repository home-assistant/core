#!/bin/bash

umask 0000

mkdir -p /usr/src/app/config

python -m homeassistant --config /usr/src/app/config
