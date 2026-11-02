"""Base class for assist satellite entities."""

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .connection_test import ConnectionTestView
from .const import (
    CONNECTION_TEST_DATA,
    DATA_COMPONENT,
    DOMAIN,
    PREANNOUNCE_FILENAME,
    PREANNOUNCE_URL,
    AssistSatelliteEntityFeature,
    AssistSatelliteService,
    AssistSatelliteServiceArgument,
)
from .entity import (
    AssistSatelliteAnnouncement,
    AssistSatelliteAnswer,
    AssistSatelliteConfiguration,
    AssistSatelliteEntity,
    AssistSatelliteEntityDescription,
    AssistSatelliteWakeWord,
)
from .errors import SatelliteBusyError
from .services import async_setup_services
from .websocket_api import async_register_websocket_api

__all__ = [
    "DOMAIN",
    "AssistSatelliteAnnouncement",
    "AssistSatelliteAnswer",
    "AssistSatelliteConfiguration",
    "AssistSatelliteEntity",
    "AssistSatelliteEntityDescription",
    "AssistSatelliteEntityFeature",
    "AssistSatelliteService",
    "AssistSatelliteServiceArgument",
    "AssistSatelliteWakeWord",
    "SatelliteBusyError",
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    component = hass.data[DATA_COMPONENT] = EntityComponent[AssistSatelliteEntity](
        _LOGGER, DOMAIN, hass
    )
    await component.async_setup(config)

    async_setup_services(hass)

    hass.data[CONNECTION_TEST_DATA] = {}
    async_register_websocket_api(hass)
    hass.http.register_view(ConnectionTestView())

    # Default preannounce sound
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                PREANNOUNCE_URL, str(Path(__file__).parent / PREANNOUNCE_FILENAME)
            )
        ]
    )

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
