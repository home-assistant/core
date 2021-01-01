"""Kuler Sky light platform."""
import asyncio
from datetime import timedelta
import logging
from typing import Callable, List

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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_KULERSKY = SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_WHITE_VALUE

DISCOVERY_INTERVAL = timedelta(seconds=60)

PARALLEL_UPDATES = 0


def check_light(light: pykulersky.Light):
    """Attempt to connect to this light and read the color."""
    light.connect()
    light.get_color()


async def async_setup_entry(
    hass: HomeAssistantType,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Kuler sky light devices."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "devices" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["devices"] = set()
    if "discovery" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["discovery"] = asyncio.Lock()

    async def discover(*args):
        """Attempt to discover new lights."""
        # Since discovery needs to connect to all discovered bluetooth devices, and
        # only rules out devices after a timeout, it can potentially take a long
        # time. If there's already a discovery running, just skip this poll.
        if hass.data[DOMAIN]["discovery"].locked():
            return

        async with hass.data[DOMAIN]["discovery"]:
            bluetooth_devices = await hass.async_add_executor_job(
                pykulersky.discover_bluetooth_devices
            )

            # Filter out already connected lights
            new_devices = [
                device
                for device in bluetooth_devices
                if device["address"] not in hass.data[DOMAIN]["devices"]
            ]

            for device in new_devices:
                light = pykulersky.Light(device["address"], device["name"])
                try:
                    # If the connection fails, either this is not a Kuler Sky
                    # light, or it's bluetooth connection is currently locked
                    # by another device. If the vendor's app is connected to
                    # the light when home assistant tries to connect, this
                    # connection will fail.
                    await hass.async_add_executor_job(check_light, light)
                except pykulersky.PykulerskyException:
                    continue
                # The light has successfully connected
                hass.data[DOMAIN]["devices"].add(device["address"])
                async_add_entities([KulerskyLight(light)], update_before_add=True)

    # Start initial discovery
    hass.async_create_task(discover())

    # Perform recurring discovery of new devices
    async_track_time_interval(hass, discover, DISCOVERY_INTERVAL)


class KulerskyLight(LightEntity):
    """Representation of an Kuler Sky Light."""

    def __init__(self, light: pykulersky.Light):
        """Initialize a Kuler Sky light."""
        self._light = light
        self._hs_color = None
        self._brightness = None
        self._white_value = None
        self._available = True

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.disconnect)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        await self.hass.async_add_executor_job(self.disconnect)

    def disconnect(self, *args) -> None:
        """Disconnect the underlying device."""
        self._light.disconnect()

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

    def turn_on(self, **kwargs):
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

        self._light.set_color(*rgb, white_value)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.set_color(0, 0, 0, 0)

    def update(self):
        """Fetch new state data for this light."""
        try:
            if not self._light.connected:
                self._light.connect()
            # pylint: disable=invalid-name
            r, g, b, w = self._light.get_color()
        except pykulersky.PykulerskyException as exc:
            if self._available:
                _LOGGER.warning("Unable to connect to %s: %s", self._light.address, exc)
            self._available = False
            return
        if not self._available:
            _LOGGER.info("Reconnected to %s", self.entity_id)
            self._available = True

        hsv = color_util.color_RGB_to_hsv(r, g, b)
        self._hs_color = hsv[:2]
        self._brightness = int(round((hsv[2] / 100) * 255))
        self._white_value = w
