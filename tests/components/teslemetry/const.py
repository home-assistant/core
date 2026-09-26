"""Constants for the teslemetry tests."""

from homeassistant.components.teslemetry.const import DOMAIN, TeslemetryState
from homeassistant.const import CONF_ACCESS_TOKEN

from tests.common import load_json_object_fixture

UNIQUE_ID = "abc-123"
CONFIG_V1 = {CONF_ACCESS_TOKEN: "abc-123"}

WAKE_UP_ONLINE = {"response": {"state": TeslemetryState.ONLINE}, "error": None}

PRODUCTS = load_json_object_fixture("products.json", DOMAIN)
PRODUCTS_MODERN = load_json_object_fixture("products.json", DOMAIN)
PRODUCTS_MODERN["response"][0]["command_signing"] = "required"
PRODUCTS_CYBERTRUCK = load_json_object_fixture("products.json", DOMAIN)
PRODUCTS_CYBERTRUCK["response"][0]["vehicle_config"]["car_type"] = "cybertruck"
VEHICLE_DATA = load_json_object_fixture("vehicle_data.json", DOMAIN)
VEHICLE_DATA_ASLEEP = load_json_object_fixture("vehicle_data.json", DOMAIN)
VEHICLE_DATA_ASLEEP["response"]["state"] = TeslemetryState.OFFLINE
VEHICLE_DATA_ALT = load_json_object_fixture("vehicle_data_alt.json", DOMAIN)
VEHICLE_DATA_NONE = load_json_object_fixture("vehicle_data.json", DOMAIN)
VEHICLE_DATA_NONE["response"]["vehicle_state"]["ft"] = None
VEHICLE_DATA_NONE["response"]["vehicle_state"]["rt"] = None
VEHICLE_DATA_NONE["response"]["charge_state"]["charge_port_door_open"] = None
LIVE_STATUS = load_json_object_fixture("live_status.json", DOMAIN)
SITE_INFO = load_json_object_fixture("site_info.json", DOMAIN)
SITE_INFO_WEEK_CROSSING = load_json_object_fixture(
    "site_info_week_crossing.json", DOMAIN
)
SITE_INFO_MULTI_SEASON = load_json_object_fixture("site_info_multi_season.json", DOMAIN)

# The site-local day the streamed energy_totals fixtures below belong to. The
# site timezone site_info.json declares is deliberately not the test machine's.
ENERGY_TOTALS_DATE = "2024-09-18"

# A valid, non-empty day: the server sums every period itself and sends 0 for a
# field that never appeared.
ENERGY_TOTALS = {
    "solar_energy_exported": 724,
    "generator_energy_exported": 0,
    "grid_energy_imported": 0,
    "grid_services_energy_imported": 0,
    "grid_services_energy_exported": 0,
    "grid_energy_exported_from_solar": 2,
    "grid_energy_exported_from_generator": 0,
    "grid_energy_exported_from_battery": 0,
    "battery_energy_exported": 36,
    "battery_energy_imported_from_grid": 0,
    "battery_energy_imported_from_solar": 684,
    "battery_energy_imported_from_generator": 0,
    "consumer_energy_imported_from_grid": 0,
    "consumer_energy_imported_from_solar": 38,
    "consumer_energy_imported_from_battery": 36,
    "consumer_energy_imported_from_generator": 0,
    "total_home_usage": 74,
    "total_battery_charge": 684,
    "total_battery_discharge": 36,
    "total_solar_generation": 724,
    "total_grid_energy_exported": 2,
}

# An empty or malformed day: every field comes back null.
ENERGY_TOTALS_NULL = dict.fromkeys(ENERGY_TOTALS)

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

# Per-vehicle config cache returned in the metadata endpoint. The select
# platform reads rear_seat_heaters and third_row_seats to decide which rear
# seat-heater entities exist. Defaults match the Model 3 in vehicle_data.json
# (heated rear bench, no third row, no seat cooling).
VEHICLE_CONFIG = {
    "rear_seat_heaters": 1,
    "third_row_seats": "None",
    "has_seat_cooling": False,
}

METADATA = {
    "uid": UNIQUE_ID,
    "region": "NA",
    "scopes": [
        "openid",
        "offline_access",
        "user_data",
        "vehicle_device_data",
        "vehicle_cmds",
        "vehicle_charging_cmds",
        "vehicle_location",
        "energy_device_data",
        "energy_cmds",
    ],
    "vehicles": {
        "LRW3F7EK4NC700000": {
            "proxy": True,
            "access": True,
            "polling": False,
            "firmware": "2026.0.0",
            "discounted": False,
            "fleet_telemetry": "1.0.2",
            "name": "Home Assistant",
            "config": VEHICLE_CONFIG,
        }
    },
    "energy_sites": {
        "123456": {
            "access": True,
            "name": "Energy Site",
        }
    },
}
METADATA_LEGACY = {
    "uid": UNIQUE_ID,
    "region": "NA",
    "scopes": [
        "openid",
        "offline_access",
        "user_data",
        "vehicle_device_data",
        "vehicle_cmds",
        "vehicle_charging_cmds",
        "vehicle_location",
        "energy_device_data",
        "energy_cmds",
    ],
    "vehicles": {
        "LRW3F7EK4NC700000": {
            "proxy": False,
            "access": True,
            "polling": True,
            "firmware": "2026.0.0",
            "discounted": True,
            "fleet_telemetry": "unknown",
            "name": "Home Assistant",
            "config": VEHICLE_CONFIG,
        }
    },
    "energy_sites": {
        "123456": {
            "access": True,
            "name": "Energy Site",
        }
    },
}
METADATA_NOSCOPE = {
    "uid": UNIQUE_ID,
    "region": "NA",
    "scopes": ["openid", "offline_access", "vehicle_device_data"],
    "vehicles": {
        "LRW3F7EK4NC700000": {
            "proxy": False,
            "access": True,
            "polling": True,
            "firmware": "2026.0.0",
            "discounted": True,
            "fleet_telemetry": "unknown",
            "name": "Home Assistant",
            "config": VEHICLE_CONFIG,
        }
    },
    "energy_sites": {
        "123456": {
            "access": True,
            "name": "Energy Site",
        }
    },
}

# Energy-only account: no accessible vehicle, one accessible energy site.
METADATA_ENERGY = {
    "uid": UNIQUE_ID,
    "region": "NA",
    "scopes": [
        "openid",
        "offline_access",
        "user_data",
        "energy_device_data",
        "energy_cmds",
    ],
    "vehicles": {},
    "energy_sites": {
        "123456": {
            "access": True,
            "name": "Energy Site",
        }
    },
}
PRODUCTS_ENERGY = load_json_object_fixture("products.json", DOMAIN)
PRODUCTS_ENERGY["response"] = [
    product for product in PRODUCTS_ENERGY["response"] if "energy_site_id" in product
]
