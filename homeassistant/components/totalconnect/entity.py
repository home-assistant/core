"""Base class for TotalConnect entities."""

from total_connect_client.zone import TotalConnectZone

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, TotalConnectDataUpdateCoordinator


class TotalConnectEntity(CoordinatorEntity[TotalConnectDataUpdateCoordinator]):
    """Represent a TotalConnect entity."""


class TotalConnectZoneEntity(TotalConnectEntity):
    """Represent a TotalConnect zone."""

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        zone: TotalConnectZone,
        location_id: str,
        key: str,
    ) -> None:
        """Initialize the TotalConnect zone."""
        super().__init__(coordinator)
        self._location_id = location_id
        self._zone = zone
        self._attr_unique_id = f"{location_id}_{zone.zoneid}_{key}"
        identifier = zone.sensor_serial_number or f"zone_{zone.zoneid}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=zone.description,
            serial_number=zone.sensor_serial_number,
        )
