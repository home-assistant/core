"""Support for Gatus binary sensors."""

from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
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

    known_endpoints: set[str] = set()

    @callback
    def _check_endpoints() -> None:
        current_endpoints = set(coordinator.data)
        new_endpoints = current_endpoints - known_endpoints
        if new_endpoints:
            known_endpoints.update(new_endpoints)
            async_add_entities(
                GatusEndpointBinarySensor(coordinator, entry, endpoint_key)
                for endpoint_key in new_endpoints
            )
        known_endpoints.intersection_update(current_endpoints)

    _check_endpoints()
    entry.async_on_unload(coordinator.async_add_listener(_check_endpoints))


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
    def is_on(self) -> bool:
        """Return true if the endpoint is up and healthy."""
        if TYPE_CHECKING:
            assert self.latest_result is not None

        return self.latest_result.success
