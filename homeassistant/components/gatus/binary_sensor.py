"""Support for Gatus binary sensors."""

from typing import override

from gatus_api import EndpointStatus, Result

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GatusConfigEntry, GatusDataUpdateCoordinator

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


class GatusEndpointBinarySensor(
    CoordinatorEntity[GatusDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Gatus endpoint status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: GatusConfigEntry,
        endpoint_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._endpoint_key = endpoint_key

        endpoint_data = self.endpoint_data

        endpoint_name = endpoint_data.name
        if endpoint_data.group is not None:
            device_name = f"{endpoint_data.group} {endpoint_name}"
        else:
            device_name = endpoint_name

        self._attr_unique_id = f"{entry.entry_id}_{endpoint_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{endpoint_key}")},
            name=device_name,
            manufacturer="Gatus",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the endpoint is up and healthy."""
        latest_result = self.latest_result
        if latest_result is None:
            return None

        return latest_result.success

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        data = self.coordinator.data
        # Guard for empty results list, which could imply a brand new endpoint
        return (
            super().available
            and self._endpoint_key in data
            and bool(data[self._endpoint_key].results)
        )

    @property
    def endpoint_data(self) -> EndpointStatus:
        """Return this specific endpoint's data from the coordinator."""
        return self.coordinator.data[self._endpoint_key]

    @property
    def latest_result(self) -> Result | None:
        """Return the most recent monitoring result (Gatus appends newest last)."""
        results = self.endpoint_data.results
        if not results:
            return None
        return results[-1]
