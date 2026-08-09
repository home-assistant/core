"""Support for Gatus sensors."""

from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GatusConfigEntry, GatusDataUpdateCoordinator
from .entity import GatusEndpointEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Gatus sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        GatusEndpointResponseTimeSensor(coordinator, entry, endpoint_key)
        for endpoint_key in coordinator.data
    )


class GatusEndpointResponseTimeSensor(GatusEndpointEntity, SensorEntity):
    """Representation of a Gatus endpoint response time sensor."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "response_time"

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: GatusConfigEntry,
        endpoint_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, endpoint_key)
        self._attr_unique_id = f"{entry.entry_id}_{endpoint_key}_response_time"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the response time in milliseconds."""
        if TYPE_CHECKING:
            assert self.latest_result is not None
        if (duration := self.latest_result.duration) is None:
            return None

        return round(duration / 1_000_000, 2)
