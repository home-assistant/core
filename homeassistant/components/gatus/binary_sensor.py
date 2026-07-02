"""Support for Gatus binary sensors."""

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GatusDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Gatus binary sensor platform."""
    coordinator: GatusDataUpdateCoordinator = entry.runtime_data

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

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: ConfigEntry,
        endpoint_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._endpoint_key = endpoint_key

        # Check group is defined for this endpoint Note: Group is optional
        if "group" in self.endpoint_data:
            group = self.endpoint_data["group"]
            if group is not None:
                self._attr_name = f"{group} {self.endpoint_data['name']}"
        else:
            self._attr_name = f"{self.endpoint_data['name']}"

        self._attr_unique_id = f"{entry.entry_id}_{endpoint_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Gatus",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the endpoint is up and healthy."""
        latest_result = self.latest_result
        if TYPE_CHECKING:
            assert latest_result is not None

        return latest_result["success"]

    @property
    def endpoint_data(self) -> dict[str, Any]:
        """Return this specific endpoint's data from the coordinator."""
        return self.coordinator.data[self._endpoint_key]

    @property
    def latest_result(self) -> dict[str, Any]:
        """Return the most recent monitoring result (Gatus appends newest last)."""
        results = self.endpoint_data["results"]
        return results[-1]
