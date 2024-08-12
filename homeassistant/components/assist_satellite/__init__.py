"""Base class for assist satellite entities."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .entity import AssistSatelliteEntity
from .models import AssistSatelliteEntityFeature, AssistSatelliteState, SatelliteConfig

__all__ = [
    "DOMAIN",
    "AssistSatelliteEntityFeature",
    "AssistSatelliteState",
    "AssistSatelliteEntity",
    "SatelliteConfig",
]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    component = hass.data[DOMAIN] = EntityComponent[AssistSatelliteEntity](
        _LOGGER, DOMAIN, hass
    )
    await component.async_setup(config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


def async_get_satellite_entity(
    hass: HomeAssistant, domain: str, unique_id_prefix: str
) -> AssistSatelliteEntity | None:
    """Get Assist satellite entity."""
    ent_reg = er.async_get(hass)
    satellite_entity_id = ent_reg.async_get_entity_id(
        Platform.ASSIST_SATELLITE, domain, f"{unique_id_prefix}-assist_satellite"
    )
    if satellite_entity_id is None:
        return None

    component: EntityComponent[AssistSatelliteEntity] = hass.data[DOMAIN]
    return component.get_entity(satellite_entity_id)
