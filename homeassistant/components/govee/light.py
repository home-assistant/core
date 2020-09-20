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
)  # add supports

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

    # TODO: check status every interval


class GoveeLightEntity(LightEntity):
    """ representation of a stateful light entity """

    def __init__(self, hub: Govee, title: str, device: GoveeDevice):
        """ init a Govee light strip """
        self._hub = hub
        self._title = title
        self._device = device
        self._is_on = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return 0  # SUPPORT_BRIGHTNESS, ....

    async def async_update(self):
        """ get state of the led strip """
        _LOGGER.debug(f"async_turn_on for Govee light {self._device.device}")
        state, err = await self._hub.get_state(self._device)
        if state:
            self._is_on = state.power_state
            # TODO: other states
        else:
            _LOGGER.warn(f"cannot get state for {self._device.device}")

    async def async_turn_on(self, **kwargs):
        """Turn device on."""
        _LOGGER.debug(f"async_turn_on for Govee light {self._device.device}")
        success, err = await self._hub.turn_on(self._device)
        if success:
            self._is_on = True

    async def async_turn_off(self, **kwargs):
        """Turn device off."""
        _LOGGER.debug(f"async_turn_off for Govee light {self._device.device}")
        success, err = await self._hub.turn_off(self._device)
        if success:
            self._is_on = False

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
            # "sw_version": self.light.raw["swversion"],
            "via_device": (DOMAIN, "Govee API (cloud)"),
        }

    @property
    def is_on(self):
        return self._is_on
