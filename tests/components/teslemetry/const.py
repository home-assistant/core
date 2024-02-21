"""Constants for the teslemetry tests."""

from homeassistant.components.teslemetry.const import DOMAIN, TeslemetryState
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import load_json_object_fixture

CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}

WAKE_UP_ONLINE = {"response": {"state": TeslemetryState.ONLINE}, "error": None}
WAKE_UP_ASLEEP = {"response": {"state": TeslemetryState.ASLEEP}, "error": None}

PRODUCTS = load_json_object_fixture("products.json", DOMAIN)
VEHICLE_DATA = load_json_object_fixture("vehicle_data.json", DOMAIN)

RESPONSE_OK = {"response": {}, "error": None}
