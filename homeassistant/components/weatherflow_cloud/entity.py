"""Base entity class for WeatherFlow Cloud integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WeatherFlowCloudDataUpdateCoordinator


def get_station_device_info(station_name: str, station_id: int) -> DeviceInfo:
    """Generate attr_device_info from station name/id.."""
    return DeviceInfo(
        name=station_name,
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, str(station_id))},
        manufacturer=MANUFACTURER,
        configuration_url=f"https://tempestwx.com/station/{station_id}/grid",
    )


class WeatherFlowCloudEntity(CoordinatorEntity[WeatherFlowCloudDataUpdateCoordinator]):
    """Base entity class to use for sensors."""

    _attr_attribution = ATTR_ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WeatherFlowCloudDataUpdateCoordinator,
        description: EntityDescription,
        station_id: int,
        is_sensor: bool = True,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.station_id = station_id

        station_name = self.coordinator.data[station_id].station.name

        if is_sensor:
            self._attr_unique_id = f"{station_name}_{description.key}"
        else:
            self._attr_unique_id = f"weatherflow_forecast_{station_id}"

        self._attr_device_info = DeviceInfo(
            name=station_name,
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(station_id))},
            manufacturer=MANUFACTURER,
            configuration_url=f"https://tempestwx.com/station/{station_id}/grid",
        )
