"""Constants for Genius Hub."""

from datetime import timedelta
from enum import StrEnum

from homeassistant.components.climate import PRESET_ACTIVITY, PRESET_BOOST, HVACMode
from homeassistant.const import STATE_OFF

DOMAIN = "geniushub"

SCAN_INTERVAL = timedelta(seconds=60)

SENSOR_PREFIX = "Genius"


class GeniusHubService(StrEnum):
    """Store keys for Genius Hub services."""

    SET_ZONE_MODE = "set_zone_mode"
    SET_ZONE_MODE_WATER_HEATER = "set_zone_mode_water_heater"
    SET_ZONE_OVERRIDE = "set_zone_override"
    SET_ZONE_OVERRID_WATER_HEATER = "set_zone_override_water_heater"
    SET_SWITCH_OVERRIDE = "set_switch_override"


class GeniusHubServiceArgument(StrEnum):
    """Store keys for Genius Hub service arguments."""

    MODE = "mode"
    TEMPERATURE = "temperature"
    DURATION = "duration"


ATTR_MANUFACTURER = "GeniusHub"
IDENTIFIER_ZONE = "zone-{0}"
IDENTIFIER_DEVICE = "device-{0}"
SERIAL_NO = "{0} Id: {1}"

### __init__ Constants Start ###
MAC_ADDRESS_REGEXP = r"^([0-9A-F]{2}:){5}([0-9A-F]{2})$"
### __init__ Constants End ###

### Entity Constants Start ###
# temperature is repeated here, as it gives access to high-precision temps
GH_ZONE_ATTRS = ["mode", "temperature", "type", "occupied", "override"]
GH_DEVICE_ATTRS = {
    "luminance": "luminance",
    "measuredTemperature": "measured_temperature",
    "occupancyTrigger": "occupancy_trigger",
    "setback": "setback",
    "setTemperature": "set_temperature",
    "wakeupInterval": "wakeup_interval",
}
### Entity Constants Endt ###

### Switch Constants Start ###
GH_ON_OFF_ZONE = "on / off"
### Switch Constants End ###

### Climate Constants Start ###
# GeniusHub Zones support: Off, Timer, Override/Boost, Footprint & Linked modes
HA_HVAC_TO_GH = {
    HVACMode.OFF: "off",
    HVACMode.AUTO: "timer",
    HVACMode.HEAT: "override",
}
GH_HVAC_TO_HA = {v: k for k, v in HA_HVAC_TO_GH.items()}

HA_PRESET_TO_GH = {PRESET_ACTIVITY: "footprint", PRESET_BOOST: "override"}
GH_PRESET_TO_HA = {v: k for k, v in HA_PRESET_TO_GH.items()}

GH_ZONES = ["radiator", "wet underfloor"]
### Climate Constants End ###

### Binary Sensor Constants Start ###
GH_BINARY_SENSOR_STATE_ATTR = "outputOnOff"
GH_DUAL_CHANNEL_RECEIVER = "Dual Channel Receiver"
GH_ELECTRIC_SWITCH_TYPE = "Electric Switch"
GH_RECEIVER_TYPE = "Receiver"
### Binary Sensor Constants End ###


### Sensor Constants Start ###
GH_BATTERY_LEVEL_ATTR = "batteryLevel"

GH_LEVEL_MAPPING = {
    "error": "Errors",
    "warning": "Warnings",
    "information": "Information",
}
### Sensor Constants End ###

### Water Heater Constants Start ###
STATE_AUTO = "auto"
STATE_MANUAL = "manual"

# Genius Hub HW zones support only Off, Override/Boost & Timer modes
HA_OPMODE_TO_GH = {STATE_OFF: "off", STATE_AUTO: "timer", STATE_MANUAL: "override"}
GH_STATE_TO_HA = {
    "off": STATE_OFF,
    "timer": STATE_AUTO,
    "footprint": None,
    "away": None,
    "override": STATE_MANUAL,
    "early": None,
    "test": None,
    "linked": None,
    "other": None,
}

GH_HEATERS = ["hot water temperature"]
### Water Heater Constants End ###

GH_ATTR_NAME = "name"
GH_ATTR_SETPOINT = "setpoint"
GH_ATTR_TEMPERATURE = "temperature"
GH_TYPE = "type"
