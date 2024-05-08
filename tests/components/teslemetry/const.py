"""Constants for the teslemetry tests."""

from homeassistant.components.teslemetry.const import DOMAIN, TeslemetryState
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import load_json_object_fixture

CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}

WAKE_UP_ONLINE = {"response": {"state": TeslemetryState.ONLINE}, "error": None}
WAKE_UP_ASLEEP = {"response": {"state": TeslemetryState.ASLEEP}, "error": None}

PRODUCTS = load_json_object_fixture("products.json", DOMAIN)
VEHICLE_DATA = load_json_object_fixture("vehicle_data.json", DOMAIN)
VEHICLE_DATA_ALT = load_json_object_fixture("vehicle_data_alt.json", DOMAIN)
LIVE_STATUS = load_json_object_fixture("live_status.json", DOMAIN)

RESPONSE_OK = {"response": {}, "error": None}

METADATA = {
    "region": "NA",
    "scopes": [
        "openid",
        "offline_access",
        "user_data",
        "vehicle_device_data",
        "vehicle_cmds",
        "vehicle_charging_cmds",
        "energy_device_data",
        "energy_cmds",
    ],
}
METADATA_NOSCOPE = {
    "region": "NA",
    "scopes": ["openid", "offline_access", "vehicle_device_data"],
}
