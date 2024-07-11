"""Constants for EQ3 Bluetooth Smart Radiator Valves."""

from enum import Enum

from eq3btsmart.const import OperationMode

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

GET_DEVICE_TIMEOUT = 5  # seconds


EQ_TO_HA_HVAC: dict[OperationMode, HVACMode] = {
    OperationMode.OFF: HVACMode.OFF,
    OperationMode.ON: HVACMode.HEAT,
    OperationMode.AUTO: HVACMode.AUTO,
    OperationMode.MANUAL: HVACMode.HEAT,
}

HA_TO_EQ_HVAC = {
    HVACMode.OFF: OperationMode.OFF,
    HVACMode.AUTO: OperationMode.AUTO,
    HVACMode.HEAT: OperationMode.MANUAL,
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

SIGNAL_THERMOSTAT_DISCONNECTED = f"{DOMAIN}.thermostat_disconnected"
SIGNAL_THERMOSTAT_CONNECTED = f"{DOMAIN}.thermostat_connected"
