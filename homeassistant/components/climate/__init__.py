"""Provides functionality to interact with climate devices."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_HORIZONTAL_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    ATTR_TARGET_HUMIDITY_STEP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DATA_COMPONENT,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_HUMIDITY,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    FAN_ON,
    FAN_TOP,
    HVAC_MODES,
    INTENT_SET_FAN_MODE,
    INTENT_SET_TEMPERATURE,
    PRESET_ACTIVITY,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    ClimateEntityCapabilityAttribute,
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    HVACAction,
    HVACMode,
)
from .entity import (
    ClimateEntity,
    ClimateEntityDescription,
    ClimateExtraStoredData,
    RestoreClimate,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


__all__ = [
    "ATTR_CURRENT_HUMIDITY",
    "ATTR_CURRENT_TEMPERATURE",
    "ATTR_FAN_MODE",
    "ATTR_FAN_MODES",
    "ATTR_HUMIDITY",
    "ATTR_HVAC_ACTION",
    "ATTR_HVAC_MODE",
    "ATTR_HVAC_MODES",
    "ATTR_MAX_HUMIDITY",
    "ATTR_MAX_TEMP",
    "ATTR_MIN_HUMIDITY",
    "ATTR_MIN_TEMP",
    "ATTR_PRESET_MODE",
    "ATTR_PRESET_MODES",
    "ATTR_SWING_HORIZONTAL_MODE",
    "ATTR_SWING_HORIZONTAL_MODES",
    "ATTR_SWING_MODE",
    "ATTR_SWING_MODES",
    "ATTR_TARGET_HUMIDITY_STEP",
    "ATTR_TARGET_TEMP_HIGH",
    "ATTR_TARGET_TEMP_LOW",
    "ATTR_TARGET_TEMP_STEP",
    "ATTR_TEMPERATURE",
    "DEFAULT_MAX_HUMIDITY",
    "DEFAULT_MAX_TEMP",
    "DEFAULT_MIN_HUMIDITY",
    "DEFAULT_MIN_TEMP",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "FAN_AUTO",
    "FAN_DIFFUSE",
    "FAN_FOCUS",
    "FAN_HIGH",
    "FAN_LOW",
    "FAN_MEDIUM",
    "FAN_MIDDLE",
    "FAN_OFF",
    "FAN_ON",
    "FAN_TOP",
    "HVAC_MODES",
    "INTENT_SET_FAN_MODE",
    "INTENT_SET_TEMPERATURE",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "PRESET_ACTIVITY",
    "PRESET_AWAY",
    "PRESET_BOOST",
    "PRESET_COMFORT",
    "PRESET_ECO",
    "PRESET_HOME",
    "PRESET_NONE",
    "PRESET_SLEEP",
    "SERVICE_SET_FAN_MODE",
    "SERVICE_SET_HUMIDITY",
    "SERVICE_SET_HVAC_MODE",
    "SERVICE_SET_PRESET_MODE",
    "SERVICE_SET_SWING_HORIZONTAL_MODE",
    "SERVICE_SET_SWING_MODE",
    "SERVICE_SET_TEMPERATURE",
    "SERVICE_TOGGLE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "SWING_BOTH",
    "SWING_HORIZONTAL",
    "SWING_OFF",
    "SWING_ON",
    "SWING_VERTICAL",
    "ClimateEntity",
    "ClimateEntityCapabilityAttribute",
    "ClimateEntityDescription",
    "ClimateEntityFeature",
    "ClimateEntityStateAttribute",
    "ClimateExtraStoredData",
    "HVACAction",
    "HVACMode",
    "RestoreClimate",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up climate entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[ClimateEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
