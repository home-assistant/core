"""Base class for assist satellite entities."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .connection_test import ConnectionTestView
from .const import (
    CONNECTION_TEST_DATA,
    DATA_COMPONENT,
    DOMAIN,
    AssistSatelliteEntityFeature,
)
from .entity import (
    AssistSatelliteAnnouncement,
    AssistSatelliteConfiguration,
    AssistSatelliteEntity,
    AssistSatelliteEntityDescription,
    AssistSatelliteWakeWord,
)
from .errors import SatelliteBusyError
from .websocket_api import async_register_websocket_api

__all__ = [
    "DOMAIN",
    "AssistSatelliteAnnouncement",
    "AssistSatelliteEntity",
    "AssistSatelliteConfiguration",
    "AssistSatelliteEntityDescription",
    "AssistSatelliteEntityFeature",
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

    component.async_register_entity_service(
        "announce",
        vol.All(
            cv.make_entity_service_schema(
                {
                    vol.Optional("message"): str,
                    vol.Optional("media_id"): str,
                }
            ),
            cv.has_at_least_one_key("message", "media_id"),
        ),
        "async_internal_announce",
        [AssistSatelliteEntityFeature.ANNOUNCE],
    )
    hass.data[CONNECTION_TEST_DATA] = {}
    async_register_websocket_api(hass)
    hass.http.register_view(ConnectionTestView())

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
