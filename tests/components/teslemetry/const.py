"""Constants for the teslemetry tests."""

from homeassistant.components.teslemetry.const import DOMAIN, TeslemetryState
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import load_json_object_fixture

CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}

WAKE_UP_ONLINE = {"response": {"state": TeslemetryState.ONLINE}, "error": None}
WAKE_UP_ASLEEP = {"response": {"state": TeslemetryState.ASLEEP}, "error": None}

PRODUCTS = load_json_object_fixture("products.json", DOMAIN)
VEHICLE_DATA = load_json_object_fixture("vehicle_data.json", DOMAIN)
VEHICLE_DATA_ASLEEP = load_json_object_fixture("vehicle_data.json", DOMAIN)
VEHICLE_DATA_ASLEEP["response"]["state"] = TeslemetryState.OFFLINE
VEHICLE_DATA_ALT = load_json_object_fixture("vehicle_data_alt.json", DOMAIN)
LIVE_STATUS = load_json_object_fixture("live_status.json", DOMAIN)
SITE_INFO = load_json_object_fixture("site_info.json", DOMAIN)
ENERGY_HISTORY = load_json_object_fixture("energy_history.json", DOMAIN)
METADATA = load_json_object_fixture("metadata.json", DOMAIN)

COMMAND_OK = {"response": {"result": True, "reason": ""}}
COMMAND_REASON = {"response": {"result": False, "reason": "already closed"}}
COMMAND_IGNORED_REASON = {"response": {"result": False, "reason": "already_set"}}
COMMAND_NOREASON = {"response": {"result": False}}  # Unexpected
COMMAND_ERROR = {
    "response": None,
    "error": "vehicle unavailable: vehicle is offline or asleep",
    "error_description": "",
}
COMMAND_NOERROR = {"answer": 42}
COMMAND_ERRORS = (COMMAND_REASON, COMMAND_NOREASON, COMMAND_ERROR, COMMAND_NOERROR)

RESPONSE_OK = {"response": {}, "error": None}

METADATA = {
    "uid": "abc-123",
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
    "vehicles": {
        "LRW3F7EK4NC700000": {
            "proxy": False,
            "access": True,
            "polling": True,
            "firmware": "2024.44.25",
        }
    },
}
METADATA_NOSCOPE = {
    "uid": "abc-123",
    "region": "NA",
    "scopes": ["openid", "offline_access", "vehicle_device_data"],
    "vehicles": {
        "LRW3F7EK4NC700000": {
            "proxy": False,
            "access": True,
            "polling": True,
            "firmware": "2024.44.25",
        }
    },
}
