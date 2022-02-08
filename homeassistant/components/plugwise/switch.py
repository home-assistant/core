"""Plugwise Switch component for HomeAssistant."""
from __future__ import annotations

from typing import Any

from plugwise import Smile
from plugwise.exceptions import PlugwiseException

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN, LOGGER, SWITCH_ICON
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile switches from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities: list[PlugwiseSwitchEntity] = []
    for device_id, device_properties in coordinator.data.devices.items():
        if (
            "switches" not in device_properties
            or "relay" not in device_properties["switches"]
        ):
            continue

        entities.append(
            PlugwiseSwitchEntity(
                api,
                coordinator,
                device_properties["name"],
                device_id,
            )
        )

    async_add_entities(entities, True)


class PlugwiseSwitchEntity(PlugwiseEntity, SwitchEntity):
    """Representation of a Plugwise plug."""

    _attr_icon = SWITCH_ICON

    def __init__(
        self,
        api: Smile,
        coordinator: PlugwiseDataUpdateCoordinator,
        name: str,
        device_id: str,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, device_id)
        self._attr_unique_id = f"{device_id}-plug"
        self._members = coordinator.data.devices[device_id].get("members")
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        try:
            state_on = await self._api.set_switch_state(
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
            state_off = await self._api.set_switch_state(
                self._dev_id, self._members, "relay", "off"
            )
        except PlugwiseException:
            LOGGER.error("Error while communicating to device")
        else:
            if state_off:
                self._attr_is_on = False
                self.async_write_ha_state()

    @callback
    def _async_process_data(self) -> None:
        """Update the data from the Plugs."""
        if not (data := self.coordinator.data.devices.get(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._name)
            self.async_write_ha_state()
            return

        self._attr_is_on = data["switches"].get("relay")
        self.async_write_ha_state()
