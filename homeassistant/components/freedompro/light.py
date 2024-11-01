"""Support for Freedompro light."""

from __future__ import annotations

import json
from typing import Any

from pyfreedompro import put_state

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FreedomproDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Freedompro light."""
    api_key: str = entry.data[CONF_API_KEY]
    coordinator: FreedomproDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Device(hass, api_key, device, coordinator)
        for device in coordinator.data
        if device["type"] == "lightbulb"
    )


class Device(CoordinatorEntity[FreedomproDataUpdateCoordinator], LightEntity):
    """Representation of a Freedompro light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_on = False
    _attr_brightness = 0

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        device: dict[str, Any],
        coordinator: FreedomproDataUpdateCoordinator,
    ) -> None:
        """Initialize the Freedompro light."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._api_key = api_key
        self._attr_unique_id = device["uid"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device["uid"])},
            manufacturer="Freedompro",
            model=device["type"],
            name=device["name"],
        )
        color_mode = ColorMode.ONOFF
        if "hue" in device["characteristics"]:
            color_mode = ColorMode.HS
        elif "brightness" in device["characteristics"]:
            color_mode = ColorMode.BRIGHTNESS
        self._attr_color_mode = color_mode
        self._attr_supported_color_modes = {color_mode}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["uid"] == self._attr_unique_id
            ),
            None,
        )
        if device is not None and "state" in device:
            state = device["state"]
            if "on" in state:
                self._attr_is_on = state["on"]
            if "brightness" in state:
                self._attr_brightness = round(state["brightness"] / 100 * 255)
            if "hue" in state and "saturation" in state:
                self._attr_hs_color = (state["hue"], state["saturation"])
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async function to set on to light."""
        payload: dict[str, Any] = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            payload["brightness"] = round(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
        if ATTR_HS_COLOR in kwargs:
            payload["saturation"] = round(kwargs[ATTR_HS_COLOR][1])
            payload["hue"] = round(kwargs[ATTR_HS_COLOR][0])
        await put_state(
            self._session,
            self._api_key,
            self._attr_unique_id,
            json.dumps(payload),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Async function to set off to light."""
        payload = {"on": False}
        await put_state(
            self._session,
            self._api_key,
            self._attr_unique_id,
            json.dumps(payload),
        )
        await self.coordinator.async_request_refresh()
