"""Support for Gatus binary sensors."""

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up the Gatus binary sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        GatusEndpointBinarySensor(coordinator, entry, endpoint_key)
        for endpoint_key in coordinator.data
    )


class GatusEndpointBinarySensor(GatusEndpointEntity, BinarySensorEntity):
    """Representation of a Gatus endpoint status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = None

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: GatusConfigEntry,
        endpoint_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, endpoint_key)
        self._attr_unique_id = f"{entry.entry_id}_{endpoint_key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the endpoint is up and healthy."""
        latest_result = self.latest_result
        if latest_result is None:
            return None

        return latest_result.success
