"""Support for the AEMET OpenData service."""

from aemet_opendata.const import (
    AOD_CONDITION,
    AOD_FORECAST_DAILY,
    AOD_FORECAST_HOURLY,
    AOD_HUMIDITY,
    AOD_PRESSURE,
    AOD_TEMP,
    AOD_WEATHER,
    AOD_WIND_DIRECTION,
    AOD_WIND_SPEED,
    AOD_WIND_SPEED_MAX,
)

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTRIBUTION,
    CONDITIONS_MAP,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
)
from .coordinator import WeatherUpdateCoordinator
from .entity import AemetEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AEMET OpenData weather entity based on a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    weather_coordinator = domain_data[ENTRY_WEATHER_COORDINATOR]

    async_add_entities(
        [
            AemetWeather(
                domain_data[ENTRY_NAME], config_entry.unique_id, weather_coordinator
            )
        ],
        False,
    )


class AemetWeather(
    AemetEntity,
    SingleCoordinatorWeatherEntity[WeatherUpdateCoordinator],
):
    """Implementation of an AEMET OpenData weather."""

    _attr_attribution = ATTRIBUTION
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        name,
        unique_id,
        coordinator: WeatherUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id

    @property
    def condition(self):
        """Return the current condition."""
        cond = self.get_aemet_value([AOD_WEATHER, AOD_CONDITION])
        return CONDITIONS_MAP.get(cond)

    @callback
    def _async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self.get_aemet_forecast(AOD_FORECAST_DAILY)

    @callback
    def _async_forecast_hourly(self) -> list[Forecast]:
        """Return the hourly forecast in native units."""
        return self.get_aemet_forecast(AOD_FORECAST_HOURLY)

    @property
    def humidity(self):
        """Return the humidity."""
        return self.get_aemet_value([AOD_WEATHER, AOD_HUMIDITY])

    @property
    def native_pressure(self):
        """Return the pressure."""
        return self.get_aemet_value([AOD_WEATHER, AOD_PRESSURE])

    @property
    def native_temperature(self):
        """Return the temperature."""
        return self.get_aemet_value([AOD_WEATHER, AOD_TEMP])

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        return self.get_aemet_value([AOD_WEATHER, AOD_WIND_DIRECTION])

    @property
    def native_wind_gust_speed(self):
        """Return the wind gust speed in native units."""
        return self.get_aemet_value([AOD_WEATHER, AOD_WIND_SPEED_MAX])

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        return self.get_aemet_value([AOD_WEATHER, AOD_WIND_SPEED])
