"""Platform for climate integration."""
from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .opentherm_webapi import OpenThermController


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add climate for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add all entities to HA
    async_add_entities(OpenThermClimate(controller) for controller in coordinator.data)


# https://developers.home-assistant.io/docs/core/entity/climate/
class OpenThermClimate(ClimateEntity):
    """Class that represents Climate entity."""

    controller: OpenThermController

    def __init__(
        self,
        controller: OpenThermController,
    ) -> None:
        """Initialize."""
        self.controller = controller
