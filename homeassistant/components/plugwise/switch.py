"""Plugwise Switch component for HomeAssistant."""
from __future__ import annotations

from typing import Any

from plugwise.exceptions import PlugwiseException

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, SWITCH_ICON
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile switches from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        PlugwiseSwitchEntity(coordinator, device_id)
        for device_id, device in coordinator.data.devices.items()
        if "switches" in device and "relay" in device["switches"]
    )


class PlugwiseSwitchEntity(PlugwiseEntity, SwitchEntity):
    """Representation of a Plugwise plug."""

    _attr_icon = SWITCH_ICON

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}-plug"
        self._members = coordinator.data.devices[device_id].get("members")
        self._attr_is_on = False
        self._attr_name = coordinator.data.devices[device_id].get("name")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        try:
            state_on = await self.coordinator.api.set_switch_state(
                self._dev_id, self._members, "relay", "on"
            )
        except PlugwiseException:
            LOGGER.error("Error while communicating to device")
        else:
            if state_on:
                self._attr_is_on = True
                self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        try:
            state_off = await self.coordinator.api.set_switch_state(
                self._dev_id, self._members, "relay", "off"
            )
        except PlugwiseException:
            LOGGER.error("Error while communicating to device")
        else:
            if state_off:
                self._attr_is_on = False
                self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not (data := self.coordinator.data.devices.get(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._dev_id)
            super()._handle_coordinator_update()
            return

        self._attr_is_on = data["switches"].get("relay")
        super()._handle_coordinator_update()
