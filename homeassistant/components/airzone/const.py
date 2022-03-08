"""Constants for the Airzone integration."""

from typing import Final

from aioairzone.common import OperationMode, TemperatureUnit

from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_DRY,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT

DOMAIN: Final = "airzone"
MANUFACTURER: Final = "Airzone"

AIOAIRZONE_DEVICE_TIMEOUT_SEC: Final = 10
API_TEMPERATURE_STEP: Final = 0.1
API_UPDATE_DELAY_MIN_SECONDS: Final = 3
DEFAULT_LOCAL_API_PORT: Final = 3000

HVAC_ACTION_LIB_TO_HASS: Final[dict[OperationMode, str]] = {
    OperationMode.STOP: CURRENT_HVAC_OFF,
    OperationMode.COOLING: CURRENT_HVAC_COOL,
    OperationMode.HEATING: CURRENT_HVAC_HEAT,
    OperationMode.FAN: CURRENT_HVAC_FAN,
    OperationMode.DRY: CURRENT_HVAC_DRY,
}
HVAC_MODE_LIB_TO_HASS: Final[dict[OperationMode, str]] = {
    OperationMode.STOP: HVAC_MODE_OFF,
    OperationMode.COOLING: HVAC_MODE_COOL,
    OperationMode.HEATING: HVAC_MODE_HEAT,
    OperationMode.FAN: HVAC_MODE_FAN_ONLY,
    OperationMode.DRY: HVAC_MODE_DRY,
    OperationMode.AUTO: HVAC_MODE_HEAT_COOL,
}
HVAC_MODE_HASS_TO_LIB: Final[dict[str, OperationMode]] = {
    HVAC_MODE_OFF: OperationMode.STOP,
    HVAC_MODE_COOL: OperationMode.COOLING,
    HVAC_MODE_HEAT: OperationMode.HEATING,
    HVAC_MODE_FAN_ONLY: OperationMode.FAN,
    HVAC_MODE_DRY: OperationMode.DRY,
    HVAC_MODE_HEAT_COOL: OperationMode.AUTO,
}
TEMP_UNIT_LIB_TO_HASS: Final[dict[TemperatureUnit, str]] = {
    TemperatureUnit.CELSIUS: TEMP_CELSIUS,
    TemperatureUnit.FAHRENHEIT: TEMP_FAHRENHEIT,
}
