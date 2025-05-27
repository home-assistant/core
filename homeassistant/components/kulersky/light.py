"""Kuler Sky light platform."""

from __future__ import annotations

import logging
from typing import Any

import pykulersky

from homeassistant.components import bluetooth
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kuler sky light devices."""
    ble_device = bluetooth.async_ble_device_from_address(
        hass, config_entry.data[CONF_ADDRESS], connectable=True
    )
    entity = KulerskyLight(
        config_entry.title,
        config_entry.data[CONF_ADDRESS],
        pykulersky.Light(ble_device),
    )
    async_add_entities([entity], update_before_add=True)


class KulerskyLight(LightEntity):
    """Representation of a Kuler Sky Light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_available = False
    _attr_supported_color_modes = {ColorMode.RGBW}
    _attr_color_mode = ColorMode.RGBW

    def __init__(self, name: str, address: str, light: pykulersky.Light) -> None:
        """Initialize a Kuler Sky light."""
        self._light = light
        self._attr_unique_id = address
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
            manufacturer="Brightech",
            name=name,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        try:
            await self._light.disconnect()
        except pykulersky.PykulerskyException:
            _LOGGER.debug(
                "Exception disconnected from %s", self._attr_unique_id, exc_info=True
            )

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self.brightness is not None and self.brightness > 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        default_rgbw = (255,) * 4 if self.rgbw_color is None else self.rgbw_color
        rgbw = kwargs.get(ATTR_RGBW_COLOR, default_rgbw)

        default_brightness = 0 if self.brightness is None else self.brightness
        brightness = kwargs.get(ATTR_BRIGHTNESS, default_brightness)

        if brightness == 0 and not kwargs:
            # If the light would be off, and no additional parameters were
            # passed, just turn the light on full brightness.
            brightness = 255
            rgbw = (255,) * 4

        rgbw_scaled = [round(x * brightness / 255) for x in rgbw]

        await self._light.set_color(*rgbw_scaled)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        await self._light.set_color(0, 0, 0, 0)

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        try:
            if not self._attr_available:
                await self._light.connect()
            rgbw = await self._light.get_color()
        except pykulersky.PykulerskyException as exc:
            if self._attr_available:
                _LOGGER.warning(
                    "Unable to connect to %s: %s", self._attr_unique_id, exc
                )
            self._attr_available = False
            return
        if self._attr_available is False:
            _LOGGER.info("Reconnected to %s", self._attr_unique_id)

        self._attr_available = True
        brightness = max(rgbw)
        if not brightness:
            self._attr_rgbw_color = (0, 0, 0, 0)
        else:
            rgbw_normalized = [round(x * 255 / brightness) for x in rgbw]
            self._attr_rgbw_color = (
                rgbw_normalized[0],
                rgbw_normalized[1],
                rgbw_normalized[2],
                rgbw_normalized[3],
            )
        self._attr_brightness = brightness
