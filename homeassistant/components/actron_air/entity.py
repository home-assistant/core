"""Base entity classes for Actron Air integration."""

from actron_neo_api import ActronAirZone

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActronAirSystemCoordinator


class ActronAirEntity(CoordinatorEntity[ActronAirSystemCoordinator]):
    """Base class for Actron Air entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._serial_number = coordinator.serial_number

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return not self.coordinator.is_device_stale()


class ActronAirAcEntity(ActronAirEntity):
    """Base class for Actron Air entities."""

    def __init__(self, coordinator: ActronAirSystemCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=coordinator.data.ac_system.system_name,
            manufacturer="Actron Air",
            model_id=coordinator.data.ac_system.master_wc_model,
            sw_version=coordinator.data.ac_system.master_wc_firmware_version,
            serial_number=self._serial_number,
        )


class ActronAirZoneEntity(ActronAirEntity):
    """Base class for Actron Air zone entities."""

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        zone: ActronAirZone,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._zone_id: int = zone.zone_id
        self._zone_identifier = f"{self._serial_number}_zone_{zone.zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._zone_identifier)},
            name=zone.title,
            manufacturer="Actron Air",
            model="Zone",
            suggested_area=zone.title,
            via_device=(DOMAIN, self._serial_number),
        )
