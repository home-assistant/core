"""Platform for water heater integration."""
from __future__ import annotations

from homeassistant.components.water_heater import WaterHeaterEntity
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
    """Add water_heater for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add all entities to HA
    async_add_entities(
        OpenThermWaterHeater(controller) for controller in coordinator.data
    )


# https://developers.home-assistant.io/docs/core/entity/water-heater/
class OpenThermWaterHeater(WaterHeaterEntity):
    """Class that represents WaterHeater entity."""

    controller: OpenThermController

    def __init__(
        self,
        controller: OpenThermController,
    ) -> None:
        """Initiatlize."""
        self.controller = controller
