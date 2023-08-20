import asyncio
import logging

import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA,
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# Modify these constants according to your solar marquee's Bluetooth profile and attributes
DEVICE_ADDRESS = "XX:XX:XX:XX:XX:XX"
BLE_MARQUEE_SERVICE_UUID = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
BLE_ROLL_OUT_CHARACTERISTIC = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
BLE_ROLL_UP_CHARACTERISTIC = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"


_TODO_SOLARBEAKER_NAME = "Kindhome solarbeaker"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the Bluetooth Solar Marquee platform."""
    async_add_entities([KindhomeSolarbeaker(_TODO_SOLARBEAKER_NAME)])


class KindhomeSolarbeaker(CoverEntity):
    def __init__(self, name):
        self._name = name
        self._is_open = None

    # TODO is this class ok?
    @property
    def device_class(self):
        return CoverDeviceClass.SHADE

    @property
    def supported_features(self):
        return (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

    @property
    def name(self):
        """Return the name of the marquee."""
        return self._name

    @property
    def is_opening(self):
        """Return if the marquee is opening or not."""
        return False  # Implement Bluetooth communication to get the actual state

    @property
    def is_closing(self):
        """Return if the marquee is closing or not."""
        return False  # Implement Bluetooth communication to get the actual state

    @property
    def is_closed(self):
        """Return if the marquee is closed."""
        return not self._is_open

    async def async_open_cover(self, **kwargs):
        """Open the marquee."""
        # Implement Bluetooth communication to extend the marquee
        # Update self._is_open accordingly
        self._is_open = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Close the marquee."""
        # Implement Bluetooth communication to retract the marquee
        # Update self._is_open accordingly
        self._is_open = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""

    async def async_update(self):
        """Fetch the latest state."""
        # Implement Bluetooth communication to get the latest state
        # Update self._is_open accordingly
