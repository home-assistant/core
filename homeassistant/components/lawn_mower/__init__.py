"""The lawn mower integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    SERVICE_STOP,
    LawnMowerActivity,
    LawnMowerEntityFeature,
    LawnMowerService,
)
from .entity import LawnMowerEntity, LawnMowerEntityEntityDescription
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=60)

__all__ = [
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "SERVICE_DOCK",
    "SERVICE_PAUSE",
    "SERVICE_START_MOWING",
    "SERVICE_STOP",
    "LawnMowerActivity",
    "LawnMowerEntity",
    "LawnMowerEntityEntityDescription",
    "LawnMowerEntityFeature",
    "LawnMowerService",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the lawn_mower component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[LawnMowerEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up lawn mower devices."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)
