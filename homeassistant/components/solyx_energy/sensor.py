"""Sensor entities for the Solyx Energy Nymo integration."""

from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import SensorEntity

from .entity import SolyxNymoEntity
from .entity_descriptions import SENSOR_DESCRIPTIONS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from . import SolyxEnergyConfigEntry
    from .coordinator import SolyxEnergyCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SolyxEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solyx Energy sensors from a config entry."""
    coordinator: SolyxEnergyCoordinator = entry.runtime_data
    async_add_entities(
        SolyxSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SolyxSensorEntity(SolyxNymoEntity, SensorEntity):
    """A single Solyx Energy sensor entity."""

    @property
    @override
    def native_value(self) -> StateType | None:
        """Retrieve the parsed (native) value of the sensor."""
        return getattr(self.coordinator.data, self.entity_description.key, None)
