"""Constants for the Tesla Fleet tests."""

from homeassistant.components.tesla_fleet.const import DOMAIN, TeslaFleetState

from tests.common import load_json_object_fixture

VEHICLE_ONLINE = {"response": {"state": TeslaFleetState.ONLINE}, "error": None}
VEHICLE_ASLEEP = {"response": {"state": TeslaFleetState.ASLEEP}, "error": None}

PRODUCTS = load_json_object_fixture("products.json", DOMAIN)
VEHICLE_DATA = load_json_object_fixture("vehicle_data.json", DOMAIN)
VEHICLE_DATA_ALT = load_json_object_fixture("vehicle_data_alt.json", DOMAIN)
LIVE_STATUS = load_json_object_fixture("live_status.json", DOMAIN)
ENERGY_HISTORY = load_json_object_fixture("energy_history.json", DOMAIN)
SITE_INFO = load_json_object_fixture("site_info.json", DOMAIN)

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
