#!/bin/bash

pylint homeassistant
flake8 homeassistant --exclude bower_components,external
python3 -m unittest discover ha_test
