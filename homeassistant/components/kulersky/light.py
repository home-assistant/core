"""Kuler Sky light platform."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Callable

import pykulersky

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from .const import DATA_ADDRESSES, DATA_DISCOVERY_SUBSCRIPTION, DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_KULERSKY = SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_WHITE_VALUE

DISCOVERY_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Entity], bool], None],
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
    """Representation of an Kuler Sky Light."""

    def __init__(self, light: pykulersky.Light):
        """Initialize a Kuler Sky light."""
        self._light = light
        self._hs_color = None
        self._brightness = None
        self._white_value = None
        self._available = None

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
    def name(self):
        """Return the display name of this light."""
        return self._light.name

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._light.address

    @property
    def device_info(self):
        """Device info for this light."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Brightech",
        }

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_KULERSKY

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color."""
        return self._hs_color

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._white_value

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._brightness > 0 or self._white_value > 0

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        default_hs = (0, 0) if self._hs_color is None else self._hs_color
        hue_sat = kwargs.get(ATTR_HS_COLOR, default_hs)

        default_brightness = 0 if self._brightness is None else self._brightness
        brightness = kwargs.get(ATTR_BRIGHTNESS, default_brightness)

        default_white_value = 255 if self._white_value is None else self._white_value
        white_value = kwargs.get(ATTR_WHITE_VALUE, default_white_value)

        if brightness == 0 and white_value == 0 and not kwargs:
            # If the light would be off, and no additional parameters were
            # passed, just turn the light on full brightness.
            brightness = 255
            white_value = 255

        rgb = color_util.color_hsv_to_RGB(*hue_sat, brightness / 255 * 100)

        await self._light.set_color(*rgb, white_value)

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        await self._light.set_color(0, 0, 0, 0)

    async def async_update(self):
        """Fetch new state data for this light."""
        try:
            if not self._available:
                await self._light.connect()
            # pylint: disable=invalid-name
            r, g, b, w = await self._light.get_color()
        except pykulersky.PykulerskyException as exc:
            if self._available:
                _LOGGER.warning("Unable to connect to %s: %s", self._light.address, exc)
            self._available = False
            return
        if self._available is False:
            _LOGGER.info("Reconnected to %s", self._light.address)

        self._available = True
        hsv = color_util.color_RGB_to_hsv(r, g, b)
        self._hs_color = hsv[:2]
        self._brightness = int(round((hsv[2] / 100) * 255))
        self._white_value = w
