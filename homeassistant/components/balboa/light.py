"""Support for Balboa Spa lights."""
from __future__ import annotations

from pybalboa import SpaClient

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BalboaToggleEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa's lights."""
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]
    entities = [BalboaLightEntity(control) for control in spa.lights]
    async_add_entities(entities)


class BalboaLightEntity(BalboaToggleEntity, LightEntity):
    """Representation of a Balboa Spa light entity."""

    _attr_translation_key = "light"
