"""Support for water heater devices."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE,
    DATA_COMPONENT,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    WaterHeaterCapabilityAttribute,
    WaterHeaterEntityFeature,
    WaterHeaterService,
    WaterHeaterServiceArgument,
    WaterHeaterStateAttribute,
)
from .entity import WaterHeaterEntity, WaterHeaterEntityDescription
from .services import async_setup_services

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)


STATE_ECO = "eco"
STATE_ELECTRIC = "electric"
STATE_PERFORMANCE = "performance"
STATE_HIGH_DEMAND = "high_demand"
STATE_HEAT_PUMP = "heat_pump"
STATE_GAS = "gas"


ATTR_MAX_TEMP = "max_temp"
ATTR_MIN_TEMP = "min_temp"
ATTR_OPERATION_LIST = "operation_list"
ATTR_TARGET_TEMP_HIGH = "target_temp_high"
ATTR_TARGET_TEMP_LOW = "target_temp_low"
ATTR_TARGET_TEMP_STEP = "target_temp_step"
ATTR_CURRENT_TEMPERATURE = "current_temperature"


_LOGGER = logging.getLogger(__name__)


__all__ = [
    "ATTR_AWAY_MODE",
    "ATTR_CURRENT_TEMPERATURE",
    "ATTR_MAX_TEMP",
    "ATTR_MIN_TEMP",
    "ATTR_OPERATION_LIST",
    "ATTR_OPERATION_MODE",
    "ATTR_TARGET_TEMP_HIGH",
    "ATTR_TARGET_TEMP_LOW",
    "ATTR_TARGET_TEMP_STEP",
    "ATTR_TEMPERATURE",
    "DEFAULT_MAX_TEMP",
    "DEFAULT_MIN_TEMP",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_SET_AWAY_MODE",
    "SERVICE_SET_OPERATION_MODE",
    "SERVICE_SET_TEMPERATURE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "STATE_ECO",
    "STATE_ELECTRIC",
    "STATE_GAS",
    "STATE_HEAT_PUMP",
    "STATE_HIGH_DEMAND",
    "STATE_OFF",
    "STATE_ON",
    "STATE_PERFORMANCE",
    "WaterHeaterCapabilityAttribute",
    "WaterHeaterEntity",
    "WaterHeaterEntityDescription",
    "WaterHeaterEntityFeature",
    "WaterHeaterService",
    "WaterHeaterServiceArgument",
    "WaterHeaterStateAttribute",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up water_heater devices."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[WaterHeaterEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)
