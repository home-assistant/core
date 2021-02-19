"""Support for Vera binary sensors."""
from typing import Callable, List, Optional

import pyvera as veraApi

from homeassistant.components.binary_sensor import (
    DOMAIN as PLATFORM_DOMAIN,
    ENTITY_ID_FORMAT,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import VeraDevice
from .common import ControllerData, get_controller_data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraBinarySensor(device, controller_data)
            for device in controller_data.devices.get(PLATFORM_DOMAIN)
        ],
        True,
    )


class VeraBinarySensor(VeraDevice[veraApi.VeraBinarySensor], BinarySensorEntity):
    """Representation of a Vera Binary Sensor."""

    def __init__(
        self, vera_device: veraApi.VeraBinarySensor, controller_data: ControllerData
    ):
        """Initialize the binary_sensor."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if sensor is on."""
        return self._state

    def update(self) -> None:
        """Get the latest data and update the state."""
        super().update()
        self._state = self.vera_device.is_tripped
