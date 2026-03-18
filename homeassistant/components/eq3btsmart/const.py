"""Constants for EQ3 Bluetooth Smart Radiator Valves."""

from enum import Enum

from eq3btsmart.const import Eq3OperationMode

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    HVACMode,
)

DOMAIN = "eq3btsmart"

MANUFACTURER = "eQ-3 AG"
DEVICE_MODEL = "CC-RT-BLE-EQ"

ENTITY_KEY_DST = "dst"
ENTITY_KEY_BATTERY = "battery"
ENTITY_KEY_WINDOW = "window"
ENTITY_KEY_LOCK = "lock"
ENTITY_KEY_BOOST = "boost"
ENTITY_KEY_AWAY = "away"
ENTITY_KEY_COMFORT = "comfort"
ENTITY_KEY_ECO = "eco"
ENTITY_KEY_OFFSET = "offset"
ENTITY_KEY_WINDOW_OPEN_TEMPERATURE = "window_open_temperature"
ENTITY_KEY_WINDOW_OPEN_TIMEOUT = "window_open_timeout"
ENTITY_KEY_VALVE = "valve"
ENTITY_KEY_AWAY_UNTIL = "away_until"

GET_DEVICE_TIMEOUT = 5  # seconds

EQ_TO_HA_HVAC: dict[Eq3OperationMode, HVACMode] = {
    Eq3OperationMode.OFF: HVACMode.OFF,
    Eq3OperationMode.ON: HVACMode.HEAT,
    Eq3OperationMode.AUTO: HVACMode.AUTO,
    Eq3OperationMode.MANUAL: HVACMode.HEAT,
}

HA_TO_EQ_HVAC = {
    HVACMode.OFF: Eq3OperationMode.OFF,
    HVACMode.AUTO: Eq3OperationMode.AUTO,
    HVACMode.HEAT: Eq3OperationMode.MANUAL,
}


class Preset(str, Enum):
    """Preset modes for the eQ-3 radiator valve."""

    NONE = PRESET_NONE
    ECO = PRESET_ECO
    COMFORT = PRESET_COMFORT
    BOOST = PRESET_BOOST
    AWAY = PRESET_AWAY
    OPEN = "Open"
    LOW_BATTERY = "Low Battery"
    WINDOW_OPEN = "Window"


class CurrentTemperatureSelector(str, Enum):
    """Selector for current temperature."""

    NOTHING = "NOTHING"
    UI = "UI"
    DEVICE = "DEVICE"
    VALVE = "VALVE"
    ENTITY = "ENTITY"


class TargetTemperatureSelector(str, Enum):
    """Selector for target temperature."""

    TARGET = "TARGET"
    LAST_REPORTED = "LAST_REPORTED"


DEFAULT_CURRENT_TEMP_SELECTOR = CurrentTemperatureSelector.DEVICE
DEFAULT_TARGET_TEMP_SELECTOR = TargetTemperatureSelector.TARGET
DEFAULT_SCAN_INTERVAL = 10  # seconds
DEFAULT_AWAY_HOURS = 30 * 24

SIGNAL_THERMOSTAT_DISCONNECTED = f"{DOMAIN}.thermostat_disconnected"
SIGNAL_THERMOSTAT_CONNECTED = f"{DOMAIN}.thermostat_connected"

EQ3BT_STEP = 0.5
