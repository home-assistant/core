"""Support for Broadlink lights."""
from abc import ABC, abstractmethod
import logging

from broadlink.exceptions import BroadlinkException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_UNKNOWN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BROADLINK_COLOR_MODE_RGB = 0
BROADLINK_COLOR_MODE_WHITE = 1
BROADLINK_COLOR_MODE_SCENES = 2


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Broadlink light."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]

    if device.api.type == "LB1":
        lights = [BroadlinkLB1Light(device)]

    async_add_entities(lights)


class BroadlinkLight(LightEntity, ABC):
    """Representation of a Broadlink light."""

    def __init__(self, device):
        """Initialize the light."""
        self._device = device
        self._coordinator = device.update_manager.coordinator
        self._brightness = round(self._coordinator.data["brightness"] * 2.55)
        if self._coordinator.data["bulb_colormode"] == BROADLINK_COLOR_MODE_RGB:
            self._color_mode = COLOR_MODE_HS
        elif self._coordinator.data["bulb_colormode"] == BROADLINK_COLOR_MODE_WHITE:
            self._color_mode = COLOR_MODE_COLOR_TEMP
        else:
            # Scenes are for now not supported
            self._color_mode = COLOR_MODE_UNKNOWN
        self._hs_color = [
            self._coordinator.data["hue"],
            self._coordinator.data["saturation"],
        ]
        self._color_temp = round(
            (self._coordinator.data["colortemp"] - 2700) / 100 + 153
        )
        self._state = self._coordinator.data["pwr"]

    @property
    def name(self):
        """Return the name of the light."""
        return f"{self._device.name} Light"

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the light."""
        return False

    @property
    def available(self):
        """Return True if the light is available."""
        return self._device.update_manager.available

    @property
    def is_on(self):
        """Return True if the light is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs_color

    @property
    def color_temp(self):
        """Return the color temperature property."""
        return self._color_temp

    @property
    def should_poll(self):
        """Return True if the light has to be polled for state."""
        return False

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP

    @property
    def color_mode(self):
        """Return the current color mode property"""
        return self._color_mode

    @property
    def supported_color_modes(self):
        """Return the supported color modes"""
        return [COLOR_MODE_COLOR_TEMP, COLOR_MODE_HS]

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "manufacturer": self._device.api.manufacturer,
            "model": self._device.api.model,
            "name": self._device.name,
            "sw_version": self._device.fw_version,
        }

    @callback
    def update_data(self):
        """Update data."""
        self._brightness = round(self._coordinator.data["brightness"] * 2.55)
        if self._coordinator.data["bulb_colormode"] == BROADLINK_COLOR_MODE_RGB:
            self._color_mode = COLOR_MODE_HS
        elif self._coordinator.data["bulb_colormode"] == BROADLINK_COLOR_MODE_WHITE:
            self._color_mode = COLOR_MODE_COLOR_TEMP
        else:
            # Scenes are for now not supported
            self._color_mode = COLOR_MODE_UNKNOWN
        self._hs_color = [
            self._coordinator.data["hue"],
            self._coordinator.data["saturation"],
        ]
        self._color_temp = round(
            (self._coordinator.data["colortemp"] - 2700) / 100 + 153
        )
        self._state = self._coordinator.data["pwr"]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when the light is added to hass."""
        self.async_on_remove(self._coordinator.async_add_listener(self.update_data))

    async def async_update(self):
        """Update the light."""
        await self._coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        hs_color = [int(i) for i in kwargs.get(ATTR_HS_COLOR, self._hs_color)]
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        color_temp = kwargs.get(ATTR_COLOR_TEMP, self._color_temp)
        if ATTR_COLOR_TEMP in kwargs:
            color_mode = COLOR_MODE_COLOR_TEMP
        elif ATTR_HS_COLOR in kwargs:
            color_mode = COLOR_MODE_HS
        else:
            color_mode = self._color_mode

        data = {
            "hue": hs_color[0],
            "saturation": hs_color[1],
            "colortemp": (color_temp - 153) * 100 + 2700,
            "brightness": round(brightness / 2.55),
            "pwr": 1,
            "bulb_colormode": BROADLINK_COLOR_MODE_SCENES,
        }

        if color_mode == COLOR_MODE_HS:
            data["bulb_colormode"] = BROADLINK_COLOR_MODE_RGB
        elif color_mode == COLOR_MODE_COLOR_TEMP:
            data["bulb_colormode"] = BROADLINK_COLOR_MODE_WHITE

        if await self._async_send_packet(data):
            self._hs_color = hs_color
            self._brightness = brightness
            self._color_mode = color_mode
            self._color_temp = color_temp
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        if await self._async_send_packet({"pwr": 0}):
            self._state = False
            self.async_write_ha_state()

    @abstractmethod
    async def _async_send_packet(self, request):
        """Send a packet to the device."""


class BroadlinkLB1Light(BroadlinkLight):
    """Representation of a Broadlink LB1 light."""

    def __init__(self, device):
        """Initialize the light."""
        super().__init__(device)
        self._name = f"{device.name} Light"

    @property
    def unique_id(self):
        """Return the unique id of the light."""
        return self._device.unique_id

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    async def _async_send_packet(self, request):
        """Send a packet to the device."""
        if request is None:
            return True

        try:
            await self._device.async_request(self._device.api.set_state, **request)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to send packet: %s", err)
            return False
        return True
