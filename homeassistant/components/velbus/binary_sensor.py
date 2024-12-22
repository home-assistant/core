"""Support for Velbus Binary Sensors."""

from velbusaio.channels import Button as VelbusButton

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await entry.runtime_data.scan_task
    async_add_entities(
        VelbusBinarySensor(channel)
        for channel in entry.runtime_data.controller.get_all_binary_sensor()
    )


class VelbusBinarySensor(VelbusEntity, BinarySensorEntity):
    """Representation of a Velbus Binary Sensor."""

    _channel: VelbusButton

    @property
    def is_on(self) -> bool:
        """Return true if the sensor is on."""
        return self._channel.is_closed()
