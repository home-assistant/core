"""Base entity for the National Grid US integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import NationalGridDataUpdateCoordinator


class NationalGridEntity(CoordinatorEntity[NationalGridDataUpdateCoordinator]):
    """Base entity for National Grid US."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NationalGridDataUpdateCoordinator,
        service_point_number: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._service_point_number = service_point_number
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        """Build device info for this meter."""
        meter_data = self.coordinator.data.meters.get(self._service_point_number)

        if meter_data is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self._service_point_number)},
                name=f"Meter {self._service_point_number}",
                manufacturer="National Grid",
            )

        meter = meter_data.meter
        fuel_type = meter["fuelType"].upper()

        return DeviceInfo(
            identifiers={(DOMAIN, self._service_point_number)},
            serial_number=str(meter["meterNumber"]),
            name=f"{fuel_type.title()} Meter",
            manufacturer="National Grid",
            model=f"{fuel_type.title()} {'AMI Smart Meter' if meter['hasAmiSmartMeter'] else 'Meter'}",
            configuration_url="https://myaccount.nationalgrid.com",
        )
