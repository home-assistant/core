"""Component to allow numeric input for platforms."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODE
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    AMBIGUOUS_UNITS,
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DATA_COMPONENT,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DEVICE_CLASS_UNITS,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    SERVICE_SET_VALUE,
    UNIT_CONVERTERS,
    NumberDeviceClass,
    NumberEntityCapabilityAttribute,
    NumberMode,
    NumberService,
    NumberServiceArgument,
)
from .entity import (
    NumberEntity,
    NumberEntityDescription,
    NumberExtraStoredData,
    RestoreNumber,
)
from .services import async_setup_services
from .websocket_api import async_setup as async_setup_ws_api

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


__all__ = [
    "AMBIGUOUS_UNITS",
    "ATTR_MAX",
    "ATTR_MIN",
    "ATTR_MODE",
    "ATTR_STEP",
    "ATTR_VALUE",
    "DEFAULT_MAX_VALUE",
    "DEFAULT_MIN_VALUE",
    "DEFAULT_STEP",
    "DEVICE_CLASSES_SCHEMA",
    "DEVICE_CLASS_UNITS",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_SET_VALUE",
    "UNIT_CONVERTERS",
    "NumberDeviceClass",
    "NumberEntity",
    "NumberEntityCapabilityAttribute",
    "NumberEntityDescription",
    "NumberExtraStoredData",
    "NumberMode",
    "NumberService",
    "NumberServiceArgument",
    "RestoreNumber",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Number entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[NumberEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    async_setup_ws_api(hass)
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
