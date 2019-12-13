"""Support for Vera switches."""
import logging
from typing import Callable, List

from homeassistant.components.switch import (
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
    SwitchDevice,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util import convert

from . import VeraDevice
from .common import setup_device_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    setup_device_entities(
        hass=hass,
        entry=entry,
        async_add_entities=async_add_entities,
        platform=PLATFORM_DOMAIN,
        generator=VeraSwitch,
    )


class VeraSwitch(VeraDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.vera_device.switch_on()
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.vera_device.switch_off()
        self._state = False
        self.schedule_update_ha_state()

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        power = self.vera_device.power
        if power:
            return convert(power, float, 0.0)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        self._state = self.vera_device.is_switched_on()
