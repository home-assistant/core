"""Entity definition."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BaseWeatherFlowCoordinator


class WeatherFlowCloudEntity[T](CoordinatorEntity[BaseWeatherFlowCoordinator[T]]):
    """Base entity class for WeatherFlow Cloud integration."""

    _attr_attribution = "Weather data delivered by WeatherFlow/Tempest API"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BaseWeatherFlowCoordinator[T],
        station_id: int,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator)
        self.station_id = station_id

        self._attr_device_info = DeviceInfo(
            name=coordinator.get_station_name(station_id),
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(station_id))},
            manufacturer="WeatherFlow",
            configuration_url=f"https://tempestwx.com/station/{station_id}/grid",
        )
