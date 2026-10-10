"""Weather platform for Meteo.lt integration."""

from collections import defaultdict
from datetime import datetime
from typing import Any, override

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import sun
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL
from .coordinator import MeteoLtConfigEntry, MeteoLtUpdateCoordinator

_CONDITION_MAP: dict[str, str] = {
    "partly-cloudy": ATTR_CONDITION_PARTLYCLOUDY,
    "cloudy-with-sunny-intervals": ATTR_CONDITION_PARTLYCLOUDY,
    "cloudy": ATTR_CONDITION_CLOUDY,
    "thunder": ATTR_CONDITION_LIGHTNING,
    "isolated-thunderstorms": ATTR_CONDITION_LIGHTNING_RAINY,
    "thunderstorms": ATTR_CONDITION_LIGHTNING_RAINY,
    "heavy-rain-with-thunderstorms": ATTR_CONDITION_LIGHTNING_RAINY,
    "light-rain": ATTR_CONDITION_RAINY,
    "rain": ATTR_CONDITION_RAINY,
    "heavy-rain": ATTR_CONDITION_POURING,
    "light-sleet": ATTR_CONDITION_SNOWY_RAINY,
    "sleet": ATTR_CONDITION_SNOWY_RAINY,
    "freezing-rain": ATTR_CONDITION_SNOWY_RAINY,
    "hail": ATTR_CONDITION_HAIL,
    "light-snow": ATTR_CONDITION_SNOWY,
    "snow": ATTR_CONDITION_SNOWY,
    "heavy-snow": ATTR_CONDITION_SNOWY,
    "fog": ATTR_CONDITION_FOG,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeteoLtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the weather platform."""
    coordinator = entry.runtime_data

    async_add_entities([MeteoLtWeatherEntity(coordinator)])


class MeteoLtWeatherEntity(CoordinatorEntity[MeteoLtUpdateCoordinator], WeatherEntity):
    """Weather entity for Meteo.lt."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_attribution = ATTRIBUTION
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator: MeteoLtUpdateCoordinator) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)

        self._place_code = coordinator.place_code
        self._attr_unique_id = str(self._place_code)

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._place_code)},
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    def _map_condition(self, condition_code: str | None, datetime_str: str) -> str:
        """Map a meteo.lt condition code to a Home Assistant condition string."""
        if condition_code is None:
            return ATTR_CONDITION_EXCEPTIONAL
        if condition_code == "clear":
            dt = dt_util.parse_datetime(datetime_str)
            return (
                ATTR_CONDITION_SUNNY
                if sun.is_up(self.hass, dt)
                else ATTR_CONDITION_CLEAR_NIGHT
            )
        return _CONDITION_MAP.get(condition_code, ATTR_CONDITION_EXCEPTIONAL)

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.current_conditions.temperature

    @property
    @override
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self.coordinator.data.current_conditions.apparent_temperature

    @property
    @override
    def humidity(self) -> int | None:
        """Return the humidity."""
        return self.coordinator.data.current_conditions.humidity

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self.coordinator.data.current_conditions.pressure

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.data.current_conditions.wind_speed

    @property
    @override
    def wind_bearing(self) -> int | None:
        """Return the wind bearing."""
        return self.coordinator.data.current_conditions.wind_bearing

    @property
    @override
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return self.coordinator.data.current_conditions.wind_gust_speed

    @property
    @override
    def cloud_coverage(self) -> int | None:
        """Return the cloud coverage."""
        return self.coordinator.data.current_conditions.cloud_coverage

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        cc = self.coordinator.data.current_conditions
        return self._map_condition(cc.condition_code, cc.datetime)

    def _convert_forecast_data(
        self, forecast_data: Any, include_templow: bool = False
    ) -> Forecast:
        """Convert forecast timestamp data to Forecast object."""
        return Forecast(
            datetime=forecast_data.datetime,
            native_temperature=forecast_data.temperature,
            native_templow=forecast_data.temperature_low if include_templow else None,
            native_apparent_temperature=forecast_data.apparent_temperature,
            condition=self._map_condition(
                forecast_data.condition_code, forecast_data.datetime
            ),
            native_precipitation=forecast_data.precipitation,
            precipitation_probability=None,  # Not provided by API
            native_wind_speed=forecast_data.wind_speed,
            wind_bearing=forecast_data.wind_bearing,
            cloud_coverage=forecast_data.cloud_coverage,
        )

    @override
    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        # Using hourly data to create daily summaries, since
        # daily data is not provided directly
        if not self.coordinator.data:
            return None

        forecasts_by_date = defaultdict(list)
        for timestamp in self.coordinator.data.forecast_timestamps:
            date = datetime.fromisoformat(timestamp.datetime).date()
            forecasts_by_date[date].append(timestamp)

        daily_forecasts = []
        for date in sorted(forecasts_by_date.keys()):
            day_forecasts = forecasts_by_date[date]
            if not day_forecasts:
                continue

            temps = [
                ts.temperature for ts in day_forecasts if ts.temperature is not None
            ]
            max_temp = max(temps) if temps else None
            min_temp = min(temps) if temps else None

            midday_forecast = min(
                day_forecasts,
                key=lambda ts: abs(datetime.fromisoformat(ts.datetime).hour - 12),
            )

            daily_forecast = Forecast(
                datetime=day_forecasts[0].datetime,
                native_temperature=max_temp,
                native_templow=min_temp,
                native_apparent_temperature=midday_forecast.apparent_temperature,
                condition=self._map_condition(
                    midday_forecast.condition_code, midday_forecast.datetime
                ),
                # Calculate precipitation: sum if any values, else None
                native_precipitation=(
                    sum(
                        ts.precipitation
                        for ts in day_forecasts
                        if ts.precipitation is not None
                    )
                    if any(ts.precipitation is not None for ts in day_forecasts)
                    else None
                ),
                precipitation_probability=None,
                native_wind_speed=midday_forecast.wind_speed,
                wind_bearing=midday_forecast.wind_bearing,
                cloud_coverage=midday_forecast.cloud_coverage,
            )
            daily_forecasts.append(daily_forecast)

        return daily_forecasts

    @override
    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        if not self.coordinator.data:
            return None
        return [
            self._convert_forecast_data(forecast_data)
            for forecast_data in self.coordinator.data.forecast_timestamps
        ]
