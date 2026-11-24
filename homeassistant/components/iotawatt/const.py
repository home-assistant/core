"""Constants for the IoTaWatt integration."""

import json

import httpx2

DOMAIN = "iotawatt"
VOLT_AMPERE_REACTIVE_HOURS = "VARh"

CONNECTION_ERRORS = (KeyError, json.JSONDecodeError, httpx2.HTTPError)
