"""Representation of a switchMultilevel."""
import logging
from datetime import timedelta

from homeassistant.components.number import NumberEntity

from .__init__ import ZWaveMeDevice
from .const import DOMAIN
from homeassistant.helpers.dispatcher import async_dispatcher_connect

SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)
DEVICE_NAME = "switchMultilevel"


async def async_setup_entry(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    def add_new_device(new_device):
        switch = ZWaveMeNumber(new_device)
        add_entities(
            [
                switch,
            ]
        )

    async_dispatcher_connect(
        hass, "ZWAVE_ME_NEW_" + DEVICE_NAME.upper(), add_new_device
    )


class ZWaveMeNumber(ZWaveMeDevice, NumberEntity):
    """Representation of a ZWaveMe Multilevel Switch."""

    def __init__(self, device):
        """Initialize the device."""
        ZWaveMeDevice.__init__(self, device)

    @property
    def value(self):
        """Return the unit of measurement."""
        return self.device.level

    def set_value(self, value: float) -> None:
        """Update the current value."""
        self.hass.data[DOMAIN].zwave_api.send_command(
            self.device.id, "exact?level=" + str(round(value))
        )

    @property
    def name(self):
        """Return the state of the sensor."""
        return self._name
