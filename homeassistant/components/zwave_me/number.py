"""Representation of a switchMultilevel."""
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZWaveMeEntity
from .const import DOMAIN, ZWaveMePlatform

DEVICE_NAME = ZWaveMePlatform.NUMBER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""

    @callback
    def add_new_device(new_device):
        controller = hass.data[DOMAIN][config_entry.entry_id]
        switch = ZWaveMeNumber(controller, new_device)

        async_add_entities(
            [
                switch,
            ]
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"ZWAVE_ME_NEW_{DEVICE_NAME.upper()}", add_new_device
        )
    )


class ZWaveMeNumber(ZWaveMeEntity, NumberEntity):
    """Representation of a ZWaveMe Multilevel Switch."""

    @property
    def native_value(self):
        """Return the unit of measurement."""
        if self.device.level == 99:  # Scale max value
            return 100
        return self.device.level

    def set_native_value(self, value: float) -> None:
        """Update the current value."""
        self.controller.zwave_api.send_command(
            self.device.id, f"exact?level={str(round(value))}"
        )
