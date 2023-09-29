"""Kuler Sky light platform."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import pykulersky

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DATA_ADDRESSES, DATA_DISCOVERY_SUBSCRIPTION, DOMAIN

_LOGGER = logging.getLogger(__name__)

DISCOVERY_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kuler sky light devices."""

    async def discover(*args):
        """Attempt to discover new lights."""
        lights = await pykulersky.discover()

        # Filter out already discovered lights
        new_lights = [
            light
            for light in lights
            if light.address not in hass.data[DOMAIN][DATA_ADDRESSES]
        ]

        new_entities = []
        for light in new_lights:
            hass.data[DOMAIN][DATA_ADDRESSES].add(light.address)
            new_entities.append(KulerskyLight(light))

        async_add_entities(new_entities, update_before_add=True)

    # Start initial discovery
    hass.async_create_task(discover())

    # Perform recurring discovery of new devices
    hass.data[DOMAIN][DATA_DISCOVERY_SUBSCRIPTION] = async_track_time_interval(
        hass, discover, DISCOVERY_INTERVAL
    )


class KulerskyLight(LightEntity):
    """Representation of a Kuler Sky Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, light: pykulersky.Light) -> None:
        """Initialize a Kuler Sky light."""
        self._light = light
        self._available = False
        self._attr_supported_color_modes = {ColorMode.RGBW}
        self._attr_color_mode = ColorMode.RGBW

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, self.async_will_remove_from_hass
            )
        )

    async def async_will_remove_from_hass(self, *args) -> None:
        """Run when entity will be removed from hass."""
        try:
            await self._light.disconnect()
        except pykulersky.PykulerskyException:
            _LOGGER.debug(
                "Exception disconnected from %s", self._light.address, exc_info=True
            )

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._light.address

    @property
    def device_info(self) -> DeviceInfo:
        """Device info for this light."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Brightech",
            name=self._light.name,
        )

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.brightness > 0

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

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
            if not self._available:
                await self._light.connect()
            rgbw = await self._light.get_color()
        except pykulersky.PykulerskyException as exc:
            if self._available:
                _LOGGER.warning("Unable to connect to %s: %s", self._light.address, exc)
            self._available = False
            return
        if self._available is False:
            _LOGGER.info("Reconnected to %s", self._light.address)

        self._available = True
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
