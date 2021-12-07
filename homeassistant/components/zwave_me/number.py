"""Representation of a switchMultilevel."""
from datetime import timedelta
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .__init__ import ZWaveMeEntity
from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)
DEVICE_NAME = "switchMultilevel"


async def async_setup_entry(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    @callback
    def add_new_device(new_device):
        switch = ZWaveMeNumber(new_device)
        add_entities(
            [
                switch,
            ]
        )


    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )   
    )


class ZWaveMeNumber(ZWaveMeEntity, NumberEntity):
    """Representation of a ZWaveMe Multilevel Switch."""

    def __init__(self, device):
        """Initialize the device."""
        ZWaveMeEntity.__init__(self, device)

    @property
    def value(self):
        """Return the unit of measurement."""
        return self.device.level

    def set_value(self, value: float) -> None:
        """Update the current value."""
        self.hass.data[DOMAIN].zwave_api.send_command(
            self.device.id, "exact?level=" + str(round(value))
        )
