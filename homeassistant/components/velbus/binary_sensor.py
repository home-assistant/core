"""Support for Velbus Binary Sensors."""

from typing import override

from velbusaio.channels import Button as VelbusButton

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity
from .entity_discovery import (
    async_setup_platform_discovery,
    discover_binary_sensor_entities,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus binary_sensor based on config_entry."""
    await async_setup_platform_discovery(
        hass,
        entry,
        async_add_entities,
        discover_binary_sensor_entities,
        Platform.BINARY_SENSOR,
    )


class VelbusBinarySensor(VelbusEntity, BinarySensorEntity):
    """Representation of a Velbus Binary Sensor."""

    _channel: VelbusButton

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the sensor is on."""
        return self._channel.is_closed()
