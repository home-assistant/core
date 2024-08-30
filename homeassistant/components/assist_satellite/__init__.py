"""Base class for assist satellite entities."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .entity import AssistSatelliteEntity, AssistSatelliteEntityDescription
from .models import AssistSatelliteEntityFeature, AssistSatelliteState

__all__ = [
    "DOMAIN",
    "AssistSatelliteEntity",
    "AssistSatelliteEntityDescription",
    "AssistSatelliteEntityFeature",
    "AssistSatelliteState",
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    component = hass.data[DOMAIN] = EntityComponent[AssistSatelliteEntity](
        _LOGGER, DOMAIN, hass
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        "announce",
        vol.All(
            vol.Schema(
                {
                    vol.Optional("text"): str,
                    vol.Optional("media"): str,
                }
            ),
            cv.has_at_least_one_key("text", "media"),
        ),
        "async_internal_annonuce",
        [AssistSatelliteEntityFeature.ANNOUNCE],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)
