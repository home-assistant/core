"""Define constants for the SimpliSafe component."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "rainmachine"

CONF_DURATION = "duration"
CONF_DEFAULT_ZONE_RUN_TIME = "zone_run_time"
CONF_USE_APP_RUN_TIMES = "use_app_run_times"
CONF_ALLOW_INACTIVE_ZONES_TO_RUN = "allow_inactive_zones_to_run"

DATA_API_VERSIONS = "api.versions"
DATA_MACHINE_FIRMWARE_UPDATE_STATUS = "machine.firmware_update_status"
DATA_PROGRAMS = "programs"
DATA_PROVISION_SETTINGS = "provision.settings"
DATA_RESTRICTIONS_CURRENT = "restrictions.current"
DATA_RESTRICTIONS_UNIVERSAL = "restrictions.universal"
DATA_ZONES = "zones"

DEFAULT_PORT = 8080
DEFAULT_ZONE_RUN = 60 * 10

SOIL_TYPE_MAP = {
    0: "Not Set",
    1: "Clay Loam",
    2: "Silty Clay",
    3: "Clay",
    4: "Loam",
    5: "Sandy Loam",
    6: "Loamy Sand",
    7: "Sand",
    8: "Sandy Clay",
    9: "Silt Loam",
    10: "Silt",
    99: "Other",
}

SLOPE_TYPE_MAP = {
    0: "Not Set",
    1: "Flat",
    2: "Moderate",
    3: "High",
    4: "Very High",
    99: "Other",
}

SPRINKLER_TYPE_MAP = {
    0: "Not Set",
    1: "Popup Spray",
    2: "Rotors Low Rate",
    3: "Surface Drip",
    4: "Bubblers Drip",
    5: "Rotors High Rate",
    99: "Other",
}

SUN_EXPOSURE_MAP = {0: "Not Set", 1: "Full Sun", 2: "Partial Shade", 3: "Full Shade"}

VEGETATION_MAP = {
    0: "Not Set",
    1: "Not Set",
    2: "Cool Season Grass",
    3: "Fruit Trees",
    4: "Flowers",
    5: "Vegetables",
    6: "Citrus",
    7: "Bushes",
    9: "Drought Tolerant Plants",
    10: "Warm Season Grass",
    11: "Trees",
    99: "Other",
}
