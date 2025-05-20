"""Support for Vera binary sensors."""

from __future__ import annotations

import pyvera as veraApi

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import ControllerData, get_controller_data
from .entity import VeraEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraBinarySensor(device, controller_data)
            for device in controller_data.devices[Platform.BINARY_SENSOR]
        ],
        True,
    )


class VeraBinarySensor(VeraEntity[veraApi.VeraBinarySensor], BinarySensorEntity):
    """Representation of a Vera Binary Sensor."""

    _attr_is_on = False

    def __init__(
        self, vera_device: veraApi.VeraBinarySensor, controller_data: ControllerData
    ) -> None:
        """Initialize the binary_sensor."""
        VeraEntity.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    def update(self) -> None:
        """Get the latest data and update the state."""
        super().update()
        self._attr_is_on = self.vera_device.is_tripped
