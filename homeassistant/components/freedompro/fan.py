"""Support for Freedompro fan."""

from __future__ import annotations

import json
from typing import Any

from pyfreedompro import put_state

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreedomproConfigEntry, FreedomproDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FreedomproConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Freedompro fan."""
    api_key: str = entry.data[CONF_API_KEY]
    coordinator = entry.runtime_data
    async_add_entities(
        FreedomproFan(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "fan"
    )


class FreedomproFan(CoordinatorEntity[FreedomproDataUpdateCoordinator], FanEntity):
    """Representation of a Freedompro fan."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_on = False
    _attr_percentage = 0

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        device: dict[str, Any],
        coordinator: FreedomproDataUpdateCoordinator,
    ) -> None:
        """Initialize the Freedompro fan."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._api_key = api_key
        self._attr_unique_id = device["uid"]
        self._characteristics = device["characteristics"]
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, device["uid"]),
            },
            manufacturer="Freedompro",
            model=device["type"],
            name=device["name"],
        )
        self._attr_supported_features = (
            FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )
        if "rotationSpeed" in self._characteristics:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return self._attr_is_on

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
        payload = {"rotationSpeed": percentage}
        await put_state(
            self._session,
            self._api_key,
            self.unique_id,
            json.dumps(payload),
        )
        await self.coordinator.async_request_refresh()
