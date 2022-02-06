"""Plugwise Switch component for HomeAssistant."""
from __future__ import annotations

from typing import Any

from plugwise import Smile
from plugwise.exceptions import PlugwiseException

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import COORDINATOR, DOMAIN, LOGGER, SWITCH_ICON
from .entity import PlugwiseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smile switches from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []
    switch_classes = ["plug", "switch_group"]

    all_devices = api.get_all_devices()
    for dev_id, device_properties in all_devices.items():
        members = None
        model = None

        if any(
            switch_class in device_properties["types"]
            for switch_class in switch_classes
        ):
            if "plug" in device_properties["types"]:
                model = "Metered Switch"
            if "switch_group" in device_properties["types"]:
                members = device_properties["members"]
                model = "Switch Group"

            entities.append(
                GwSwitch(
                    api, coordinator, device_properties["name"], dev_id, members, model
                )
            )

    async_add_entities(entities, True)


class GwSwitch(PlugwiseEntity, SwitchEntity):
    """Representation of a Plugwise plug."""

    _attr_icon = SWITCH_ICON

    def __init__(
        self,
        api: Smile,
        coordinator: DataUpdateCoordinator,
        name: str,
        dev_id: str,
        members: list[str] | None,
        model: str | None,
    ) -> None:
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id)
        self._attr_unique_id = f"{dev_id}-plug"

        self._members = members
        self._model = model

        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        try:
            state_on = await self._api.set_relay_state(
                self._dev_id, self._members, "on"
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
            state_off = await self._api.set_relay_state(
                self._dev_id, self._members, "off"
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
        if not (data := self._api.get_device_data(self._dev_id)):
            LOGGER.error("Received no data for device %s", self._name)
            self.async_write_ha_state()
            return

        if "relay" in data:
            self._attr_is_on = data["relay"]

        self.async_write_ha_state()
