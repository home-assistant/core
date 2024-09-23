"""Base entity class for WeatherFlow Cloud integration."""

from weatherflow4py.models.rest.unified import WeatherFlowDataREST

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WeatherFlowCloudDataUpdateCoordinator


class WeatherFlowCloudEntity(CoordinatorEntity[WeatherFlowCloudDataUpdateCoordinator]):
    """Base entity class to use for everything."""

    _attr_attribution = ATTR_ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeatherFlowCloudDataUpdateCoordinator,
        station_id: int,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator)
        self.station_id = station_id

        self._attr_device_info = DeviceInfo(
            name=self.station.station.name,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(station_id))},
            manufacturer=MANUFACTURER,
            configuration_url=f"https://tempestwx.com/station/{station_id}/grid",
        )

    @property
    def station(self) -> WeatherFlowDataREST:
        """Individual Station data."""
        return self.coordinator.data[self.station_id]
