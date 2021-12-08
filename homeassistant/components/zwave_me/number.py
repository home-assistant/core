"""Representation of a switchMultilevel."""

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ZWaveMeEntity
from .const import DOMAIN


DEVICE_NAME = "switchMultilevel"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the number platform."""

    @callback
    def add_new_device(new_device):
        switch = ZWaveMeNumber(new_device)
        async_add_entities(
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
            self.device.id, f"exact?level={str(round(value))}"
        )
