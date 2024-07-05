"""Base entity class for WeatherFlow Cloud integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WeatherFlowCloudDataUpdateCoordinator


class WeatherFlowCloudEntity(CoordinatorEntity[WeatherFlowCloudDataUpdateCoordinator]):
    """Base entity class to use for sensors."""

    _attr_attribution = ATTR_ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeatherFlowCloudDataUpdateCoordinator,
        station_id: int,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)
        # self.entity_description = description
        self.station_id = station_id

        station_name = self.coordinator.data[station_id].station.name

        self._attr_device_info = DeviceInfo(
            name=station_name,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(station_id))},
            manufacturer=MANUFACTURER,
            configuration_url=f"https://tempestwx.com/station/{station_id}/grid",
        )
