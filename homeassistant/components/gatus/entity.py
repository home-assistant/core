"""Base entity for the Gatus integration."""

from typing import override

from gatus_api import EndpointStatus, Result

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GatusConfigEntry, GatusDataUpdateCoordinator


class GatusEndpointEntity(CoordinatorEntity[GatusDataUpdateCoordinator]):
    """Base class for Gatus endpoint entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: GatusConfigEntry,
        endpoint_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._endpoint_key = endpoint_key

        endpoint_data = self.endpoint_data

        device_name = (
            f"{endpoint_data.group} {endpoint_data.name}"
            if endpoint_data.group is not None
            else endpoint_data.name
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{endpoint_key}")},
            name=device_name,
            manufacturer="Gatus",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        data = self.coordinator.data
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
        return results[-1] if (results := self.endpoint_data.results) else None
