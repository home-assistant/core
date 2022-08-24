"""Support for Freedompro fan."""
from __future__ import annotations

import json
from typing import Any

from pyfreedompro import put_state

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Freedompro fan."""
    api_key = entry.data[CONF_API_KEY]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FreedomproFan(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "fan"
    )


class FreedomproFan(CoordinatorEntity, FanEntity):
    """Representation of an Freedompro fan."""

    def __init__(self, hass, api_key, device, coordinator):
        """Initialize the Freedompro fan."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._api_key = api_key
        self._attr_name = device["name"]
        self._attr_unique_id = device["uid"]
        self._characteristics = device["characteristics"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
            },
            manufacturer="Freedompro",
            model=device["type"],
            name=self.name,
        )
        self._attr_is_on = False
        self._attr_percentage = 0
        if "rotationSpeed" in self._characteristics:
            self._attr_supported_features = FanEntityFeature.SET_SPEED

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._attr_is_on

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self._attr_percentage

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["uid"] == self.unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            self._attr_is_on = state["on"]
            if "rotationSpeed" in state:
                self._attr_percentage = state["rotationSpeed"]
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Async function to turn on the fan."""
        payload = {"on": True}
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            json.dumps(payload),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Async function to turn off the fan."""
        payload = {"on": False}
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            json.dumps(payload),
        )
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        rotation_speed = {"rotationSpeed": percentage}
        payload = json.dumps(rotation_speed)
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            payload,
        )
        await self.coordinator.async_request_refresh()
