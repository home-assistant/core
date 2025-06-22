"""Support for Lutron switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronOutput


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron switch platform.

    Adds switches from the Main Repeater associated with the config_entry as
    switch entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[SwitchEntity] = []

    # Add Lutron Switches
    for area_name, device_name, device in entry_data.switches:
        entities.append(
            LutronSwitch(area_name, device_name, device, entry_data.controller)
        )

    async_add_entities(entities, True)


class LutronSwitch(LutronOutput, SwitchEntity):
    """Representation of a Lutron Switch."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._controller.output_set_level(self._lutron_device.id, 100)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._controller.output_set_level(self._lutron_device.id, 0)

    async def _request_state(self):
        """Request the state of the switch."""
        await self._controller.output_get_level(self._lutron_device.id)

    def _update_callback(self, value: float):
        """Set switch state."""
        self._attr_is_on = value > 0
        self.async_write_ha_state()
