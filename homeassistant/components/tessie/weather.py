"""Weather platform for Tessie integration."""
from __future__ import annotations

from homeassistant.components.weather import (
    WeatherEntity,
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODELS
from .coordinator import TessieStateUpdateCoordinator, TessieWeatherDataCoordinator

CONDITIONS = {
    "clouds": ATTR_CONDITION_CLOUDY,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie Weather platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    # Add Weather entities with both coordinators
    async_add_entities(
        TessieWeatherEntity(vehicle.state_coordinator, vehicle.weather_coordinator)
        for vehicle in data
    )


class TessieWeatherEntity(
    CoordinatorEntity[TessieWeatherDataCoordinator], WeatherEntity
):
    """Base class for Tessie weathers entities."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.METERS

    def __init__(
        self,
        vehiclecoordinator: TessieStateUpdateCoordinator,
        weathercoordinator: TessieWeatherDataCoordinator,
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(weathercoordinator)

        car_type = vehiclecoordinator.data["vehicle_config_car_type"]

        self._attr_unique_id = vehiclecoordinator.vin
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vehiclecoordinator.vin)},
            manufacturer="Tesla",
            configuration_url="https://my.tessie.com/",
            name=vehiclecoordinator.data["display_name"],
            model=MODELS.get(car_type, car_type),
            sw_version=vehiclecoordinator.data["vehicle_state_car_version"],
            hw_version=vehiclecoordinator.data["vehicle_config_driver_assist"],
        )

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature in native units."""
        return self.coordinator.data.get("feels_like")

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature in native units."""
        return self.coordinator.data.get("temperature")

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure in native units."""
        return self.coordinator.data.get("pressure")

    @property
    def humidity(self) -> float | None:
        """Return the humidity in native units."""
        return self.coordinator.data.get("humidity")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed in native units."""
        return self.coordinator.data.get("wind_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self.coordinator.data.get("wind_direction")

    @property
    def cloud_coverage(self) -> float | None:
        """Return the Cloud coverage in %."""
        return self.coordinator.data.get("cloudiness")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility in native units."""
        return self.coordinator.data.get("visibility")

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return CONDITIONS.get(self.coordinator.data.get("condition")
        return condition.lower() if condition else None
