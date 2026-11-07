"""Base entity for the National Grid US integration."""

from homeassistant.helpers import device_registry as dr
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
        meter_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._meter_key = meter_key
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        """Build device info for this meter."""
        meter_data = self.coordinator.data.meters[self._meter_key]
        meter = meter_data.meter
        fuel_type = meter["fuelType"].upper()
        service_point = str(meter["servicePointNumber"])

        return DeviceInfo(
            identifiers={(DOMAIN, self._meter_key)},
            via_device_id=dr.async_get_device_id_by_identifier(
                self.coordinator.hass,
                (DOMAIN, meter_data.account_id),
                config_entry_id=self.coordinator.config_entry.entry_id,
            ),
            serial_number=str(meter["meterNumber"]),
            # account_id + service point keeps the name unique across accounts
            # that may reuse the same service point number.
            name=(f"{fuel_type.title()} Meter {meter_data.account_id}-{service_point}"),
            manufacturer="National Grid",
            model=f"{fuel_type.title()} {'AMI Smart Meter' if meter['hasAmiSmartMeter'] else 'Meter'}",
            configuration_url="https://myaccount.nationalgrid.com",
        )
