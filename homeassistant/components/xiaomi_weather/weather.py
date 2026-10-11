"""Present Xiaomi observations and forecasts using Home Assistant units."""

from datetime import UTC, datetime
from typing import override

from xiaomi_weather import DailyForecastEntry, Measurement, WeatherData

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONDITIONS
from .coordinator import XiaomiWeatherConfigEntry, XiaomiWeatherCoordinator
from .entity import XiaomiWeatherEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the location's weather entity."""
    async_add_entities([XiaomiWeather(entry)])


def _measurement(value: Measurement | None, unit: str) -> float | None:
    """Only expose measurements in the declared native unit."""
    return value.value if value is not None and value.unit == unit else None


def _condition(code: str | None, time: datetime, data: WeatherData) -> str | None:
    """Use the forecast location's solar times to distinguish clear nights."""
    result = CONDITIONS.get(code or "")
    if result == "sunny":
        for day in data.iter_daily():
            rise, setting = day.sunrise, day.sunset
            if (
                rise is not None
                and setting is not None
                and time.astimezone(rise.tzinfo).date() == rise.date()
            ):
                return "sunny" if rise <= time < setting else "clear-night"
    return result


def _daily_wind(forecast: Forecast, day: DailyForecastEntry, daytime: bool) -> None:
    """Add the appropriate half-day wind when its unit is supported."""
    if day.wind_speed is not None and day.wind_speed_unit == "km/h":
        speed = day.wind_speed.from_ if daytime else day.wind_speed.to
        if speed is not None:
            forecast["native_wind_speed"] = speed
    if day.wind_direction is not None and day.wind_direction_unit == "°":
        bearing = day.wind_direction.from_ if daytime else day.wind_direction.to
        if bearing is not None:
            forecast["wind_bearing"] = bearing


class XiaomiWeather(
    XiaomiWeatherEntity, SingleCoordinatorWeatherEntity[XiaomiWeatherCoordinator]
):
    """Represent Xiaomi Weather for one city."""

    _attr_name = None
    _attr_attribution = "Weather data provided by Xiaomi Weather"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(self, entry: XiaomiWeatherConfigEntry) -> None:
        """Initialize the weather entity."""
        super().__init__(entry, "weather")

    @property
    @override
    def condition(self) -> str | None:
        """Return the normalized current condition."""
        data = self.coordinator.data
        return _condition(data.current.weather_code, data.current.pub_time, data)

    @property
    @override
    def native_temperature(self) -> float:
        """Return temperature in Celsius."""
        return self.coordinator.data.current.temperature.value

    @property
    @override
    def humidity(self) -> float | None:
        """Return relative humidity."""
        return _measurement(self.coordinator.data.current.humidity, "%")

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return pressure in hPa."""
        return _measurement(self.coordinator.data.current.pressure, "hPa")

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return wind speed in km/h."""
        return _measurement(self.coordinator.data.current.wind.speed, "km/h")

    @property
    @override
    def wind_bearing(self) -> float | None:
        """Return wind direction in degrees."""
        return _measurement(self.coordinator.data.current.wind.direction, "°")

    @property
    @override
    def native_apparent_temperature(self) -> float | None:
        """Return feels-like temperature in Celsius."""
        return _measurement(self.coordinator.data.current.feels_like, "℃")

    @property
    @override
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return self.coordinator.data.current.uv_index

    @property
    @override
    def native_visibility(self) -> float | None:
        """Return visibility in km."""
        return _measurement(self.coordinator.data.current.visibility, "km")

    @callback
    @override
    def _async_forecast_twice_daily(self) -> list[Forecast]:
        """Return independent day and night forecasts anchored to solar times."""
        forecasts: list[Forecast] = []
        for day in self.coordinator.data.iter_daily():
            for daytime, temperature, time, code in (
                (True, day.temperature_high, day.sunrise, day.day_weather_code),
                (False, day.temperature_low, day.sunset, day.night_weather_code),
            ):
                if time is None:
                    continue
                forecast: Forecast = {
                    "datetime": time.astimezone(UTC).isoformat(),
                    "is_daytime": daytime,
                }
                if temperature is not None and day.temperature_unit == "℃":
                    forecast["native_temperature"] = temperature
                if (condition := CONDITIONS.get(code or "")) is not None:
                    forecast["condition"] = (
                        "clear-night"
                        if condition == "sunny" and not daytime
                        else condition
                    )
                _daily_wind(forecast, day, daytime)
                forecasts.append(forecast)
        return forecasts

    @callback
    @override
    def _async_forecast_daily(self) -> list[Forecast]:
        """Return daily highs and lows at the location's local midnight."""
        forecasts: list[Forecast] = []
        for day in self.coordinator.data.iter_daily():
            if day.sunrise is None:
                continue
            forecast: Forecast = {
                "datetime": day.sunrise.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                .astimezone(UTC)
                .isoformat(),
            }
            if day.temperature_unit == "℃":
                if day.temperature_high is not None:
                    forecast["native_temperature"] = day.temperature_high
                if day.temperature_low is not None:
                    forecast["native_templow"] = day.temperature_low
            if (condition := CONDITIONS.get(day.day_weather_code or "")) is not None:
                forecast["condition"] = condition
            if day.precipitation_probability is not None:
                forecast["precipitation_probability"] = round(
                    day.precipitation_probability
                )
            _daily_wind(forecast, day, True)
            forecasts.append(forecast)
        return forecasts

    @callback
    @override
    def _async_forecast_hourly(self) -> list[Forecast]:
        """Return hourly forecasts aligned by the library's typed iterator."""
        data = self.coordinator.data
        forecasts: list[Forecast] = []
        for hour in data.iter_hourly():
            forecast: Forecast = {"datetime": hour.time.astimezone(UTC).isoformat()}
            if hour.temperature is not None and hour.temperature_unit == "℃":
                forecast["native_temperature"] = hour.temperature
            if (
                condition := _condition(hour.weather_code, hour.time, data)
            ) is not None:
                forecast["condition"] = condition
            # Legacy weathercn hourly wind omits its km/h unit.
            if hour.wind_speed is not None and hour.wind_speed_unit in (None, "km/h"):
                forecast["native_wind_speed"] = hour.wind_speed
            if hour.wind_direction is not None:
                forecast["wind_bearing"] = hour.wind_direction
            forecasts.append(forecast)
        return forecasts
