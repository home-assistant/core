"""Component to allow selecting an option from a list as platforms."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CYCLE,
    ATTR_OPTIONS,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_PREVIOUS,
    SelectEntityCapabilityAttribute,
    SelectService,
    SelectServiceArgument,
)
from .entity import SelectEntity, SelectEntityDescription
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

__all__ = [
    "ATTR_CYCLE",
    "ATTR_OPTION",
    "ATTR_OPTIONS",
    "DOMAIN",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_SELECT_FIRST",
    "SERVICE_SELECT_LAST",
    "SERVICE_SELECT_NEXT",
    "SERVICE_SELECT_OPTION",
    "SERVICE_SELECT_PREVIOUS",
    "SelectEntity",
    "SelectEntityCapabilityAttribute",
    "SelectEntityDescription",
    "SelectService",
    "SelectServiceArgument",
]

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Select entities."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[SelectEntity](
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
