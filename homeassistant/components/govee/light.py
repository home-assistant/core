"""  Govee LED strips platform """

from govee_api_laggat import Govee, GoveeDevice, GoveeDeviceState
from .const import DOMAIN, DATA_SCHEMA, CONF_API_KEY, CONF_DELAY

import logging
import voluptuous as vol
import asyncio
from datetime import timedelta
from homeassistant import config_entries, core, exceptions
from homeassistant.components.light import (
    LightEntity,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_HS_COLOR,
    ATTR_COLOR_TEMP,
)
from homeassistant.util import color

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)

# keep hub reference for disposing / switching / status update
HUB = None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Govee Light platform."""
    _LOGGER.debug("Setting up Govee lights")
    config = config_entry.data
    api_key = config[CONF_API_KEY]
    SCAN_INTERVAL = timedelta(seconds=config[CONF_DELAY])

    # Setup connection with devices/cloud
    HUB = await Govee.create(api_key)

    # Verify that passed in configuration works
    devices, err = await HUB.get_devices()
    if err:
        _LOGGER.error("Could not connect to Govee API: " + err)
        return

    # Add devices
    async_add_entities(
        [GoveeLightEntity(HUB, config_entry.title, device) for device in devices], True
    )


class GoveeLightEntity(LightEntity):
    """ representation of a stateful light entity """

    def __init__(self, hub: Govee, title: str, device: GoveeDevice):
        """ init a Govee light strip """
        self._hub = hub
        self._title = title
        self._device = device
        self._state = GoveeDeviceState(
            device=device.device,
            model=device.model,
            online=False,
            power_state=False,
            brightness=0,
            color=(0, 0, 0),
        )

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_COLOR_TEMP

    async def async_update(self):
        """ get state of the led strip """
        state, err = await self._hub.get_state(self._device)
        if state:
            self._state = state
        else:
            _LOGGER.warn(f"cannot get state for {self._device.device}: {err}")

    async def async_turn_on(self, **kwargs):
        """Turn device on."""
        _LOGGER.debug(
            f"async_turn_on for Govee light {self._device.device}, kwargs: {kwargs}"
        )
        success = False
        err = None
        if ATTR_RGB_COLOR in kwargs:
            col = kwargs[ATTR_RGB_COLOR]
            success, err = await self._hub.set_color(self._device, col)
            if success:
                self._state.power_state = True
                self._state.color = col
        elif ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            col = color.color_hs_to_RGB(hs_color[0], hs_color[1])
            success, err = await self._hub.set_color(self._device, col)
            if success:
                self._state.power_state = True
                self._state.color = col
        elif ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            bright100 = brightness * 100 // 255
            success, err = await self._hub.set_brightness_100(self._device, bright100)
            if success:
                self._state.power_state = bright100 > 0
                self._state.brightness = brightness
        elif ATTR_COLOR_TEMP in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP]
            success, err = await self._hub.set_color_temp(self._device, color_temp)
            # color_temp is not in state
        else:
            success, err = await self._hub.turn_on(self._device)
            if success:
                self._state.power_state = True
        # warn on any error
        if err:
            _LOGGER.warn(
                f"async_turn_on failed with '{err}' for {self._device.device}, kwargs: {kwargs}"
            )

    async def async_turn_off(self, **kwargs):
        """Turn device off."""
        _LOGGER.debug(f"async_turn_off for Govee light {self._device.device}")
        success, err = await self._hub.turn_off(self._device)
        if success:
            self._state.power_state = False

    @property
    def unique_id(self):
        """Return the unique ID """
        return f"govee_{self._title}_{self._device.device}"

    @property
    def device_id(self):
        """Return the ID """
        return self.unique_id

    @property
    def name(self):
        """Return the name """
        return self._device.device_name

    @property
    def device_info(self):
        """Return the device info """
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": "Govee",
            "model": self._device.model,
            "via_device": (DOMAIN, "Govee API (cloud)"),
        }

    @property
    def is_on(self):
        """ return true if device is on """
        return self._state.power_state

    @property
    def available(self):
        """Return if light is available."""
        return self._state.online

    @property
    def hs_color(self):
        """Return the hs color value."""
        return color.color_RGB_to_hs(
            self._state.color[0],
            self._state.color[1],
            self._state.color[2],
        )

    @property
    def rgb_color(self):
        """Return the rgb color value."""
        return [
            self._state.color[0],
            self._state.color[1],
            self._state.color[2],
        ]

    @property
    def brightness(self):
        """Return the brightness value."""
        # govee is reporting 0 to 254 - home assistant uses 1 to 255
        return self._state.brightness + 1

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return 2000

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return 9000

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            # rate limiting information on Govee API
            "rate_limit_total": self._hub.rate_limit_total,
            "rate_limit_remaining": self._hub.rate_limit_remaining,
            "rate_limit_reset_seconds": self._hub.rate_limit_reset_seconds,
            "rate_limit_reset": self._hub.rate_limit_reset,
            "rate_limit_on": self._hub.rate_limit_on,
            # general information
            "manufacturer": "Govee",
            "model": self._device.model,
        }
