"""Base class for TotalConnect entities."""

from total_connect_client.location import TotalConnectLocation
from total_connect_client.zone import TotalConnectZone

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TotalConnectDataUpdateCoordinator


class TotalConnectEntity(CoordinatorEntity[TotalConnectDataUpdateCoordinator]):
    """Represent a TotalConnect entity."""

    _attr_has_entity_name = True


class TotalConnectLocationEntity(TotalConnectEntity):
    """Represent a TotalConnect location."""

    def __init__(
        self,
        coordinator: TotalConnectDataUpdateCoordinator,
        location: TotalConnectLocation,
    ) -> None:
        """Initialize the TotalConnect location."""
        super().__init__(coordinator)
        self._location = location
        self.device = device = location.devices[location.security_device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            name=device.name,
            serial_number=device.serial_number,
        )


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
