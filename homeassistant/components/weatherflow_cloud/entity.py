"""Entity definition."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import BaseWeatherFlowCoordinator


class WeatherFlowCloudEntity[T](CoordinatorEntity[BaseWeatherFlowCoordinator[T]]):
    """Base entity class for WeatherFlow Cloud integration."""

    _attr_attribution = ATTR_ATTRIBUTION
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
            manufacturer=MANUFACTURER,
            configuration_url=f"https://tempestwx.com/station/{station_id}/grid",
        )

    #
    # @property
    # def station(self):
    #     """Individual Station data."""
    #     return self.coordinator.get_station(self.station_id)
    #     #
    #     # if isinstance(self.coordinator, WeatherFlowCloudUpdateCoordinatorREST):
    #     #     return self.coordinator.data[self.station_id]
    #     # return self.coordinator.stations[self.station_id]
