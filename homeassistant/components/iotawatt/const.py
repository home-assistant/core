"""Constants for the IoTaWatt integration."""
from __future__ import annotations

import json

import httpx

DOMAIN = "iotawatt"
VOLT_AMPERE_REACTIVE = "VAR"
VOLT_AMPERE_REACTIVE_HOURS = "VARh"

ATTR_LAST_UPDATE = "last_update"

CONNECTION_ERRORS = (KeyError, json.JSONDecodeError, httpx.HTTPError)
