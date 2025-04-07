"""Platform for retrieving meteorological data from Environment Canada."""

from __future__ import annotations

from typing import Any

from env_canada import ECWeather

from homeassistant.components.weather import (
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
    DOMAIN as WEATHER_DOMAIN,
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
from homeassistant.core import (
    HomeAssistant,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import entity_platform, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SERVICE_ENVIRONMENT_CANADA_FORECASTS
from .coordinator import ECConfigEntry, ECDataUpdateCoordinator

# Icon codes from http://dd.weatheroffice.ec.gc.ca/citypage_weather/
# docs/current_conditions_icon_code_descriptions_e.csv
ICON_CONDITION_MAP = {
    ATTR_CONDITION_SUNNY: [0, 1],
    ATTR_CONDITION_CLEAR_NIGHT: [30, 31],
    ATTR_CONDITION_PARTLYCLOUDY: [2, 3, 4, 5, 22, 32, 33, 34, 35],
    ATTR_CONDITION_CLOUDY: [10],
    ATTR_CONDITION_RAINY: [6, 9, 11, 12, 28, 36],
    ATTR_CONDITION_LIGHTNING_RAINY: [19, 39, 46, 47],
    ATTR_CONDITION_POURING: [13],
    ATTR_CONDITION_SNOWY_RAINY: [7, 14, 15, 27, 37],
    ATTR_CONDITION_SNOWY: [8, 16, 17, 18, 25, 26, 38, 40],
    ATTR_CONDITION_WINDY: [43],
    ATTR_CONDITION_FOG: [20, 21, 23, 24, 44],
    ATTR_CONDITION_HAIL: [26, 27],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ECConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    entity_registry = er.async_get(hass)

    # Remove hourly entity from legacy config entries
    if hourly_entity_id := entity_registry.async_get_entity_id(
        WEATHER_DOMAIN,
        DOMAIN,
        _calculate_unique_id(config_entry.unique_id, True),
    ):
        entity_registry.async_remove(hourly_entity_id)

    async_add_entities([ECWeatherEntity(config_entry.runtime_data.weather_coordinator)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_ENVIRONMENT_CANADA_FORECASTS,
        None,
        "_async_environment_canada_forecasts",
        supports_response=SupportsResponse.ONLY,
    )


def _calculate_unique_id(config_entry_unique_id: str | None, hourly: bool) -> str:
    """Calculate unique ID."""
    return f"{config_entry_unique_id}{'-hourly' if hourly else '-daily'}"


class ECWeatherEntity(
    SingleCoordinatorWeatherEntity[ECDataUpdateCoordinator[ECWeather]]
):
    """Representation of a weather condition."""

    _attr_has_entity_name = True
    _attr_native_pressure_unit = UnitOfPressure.KPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator: ECDataUpdateCoordinator[ECWeather]) -> None:
        """Initialize Environment Canada weather."""
        super().__init__(coordinator)
        self.ec_data = coordinator.ec_data
        self._attr_attribution = self.ec_data.metadata["attribution"]
        self._attr_translation_key = "forecast"
        self._attr_unique_id = _calculate_unique_id(
            coordinator.config_entry.unique_id, False
        )
        self._attr_device_info = coordinator.device_info

    @property
    def native_temperature(self):
        """Return the temperature."""
        if (
            temperature := self.ec_data.conditions.get("temperature", {}).get("value")
        ) is not None:
            return float(temperature)
        if (
            self.ec_data.hourly_forecasts
            and (temperature := self.ec_data.hourly_forecasts[0].get("temperature"))
            is not None
        ):
            return float(temperature)
        return None

    @property
    def humidity(self):
        """Return the humidity."""
        if self.ec_data.conditions.get("humidity", {}).get("value"):
            return float(self.ec_data.conditions["humidity"]["value"])
        return None

    @property
    def native_wind_speed(self):
        """Return the wind speed."""
        if self.ec_data.conditions.get("wind_speed", {}).get("value"):
            return float(self.ec_data.conditions["wind_speed"]["value"])
        return None

    @property
    def wind_bearing(self):
        """Return the wind bearing."""
        if self.ec_data.conditions.get("wind_bearing", {}).get("value"):
            return float(self.ec_data.conditions["wind_bearing"]["value"])
        return None

    @property
    def native_pressure(self):
        """Return the pressure."""
        if self.ec_data.conditions.get("pressure", {}).get("value"):
            return float(self.ec_data.conditions["pressure"]["value"])
        return None

    @property
    def native_visibility(self):
        """Return the visibility."""
        if self.ec_data.conditions.get("visibility", {}).get("value"):
            return float(self.ec_data.conditions["visibility"]["value"])
        return None

    @property
    def condition(self):
        """Return the weather condition."""
        icon_code = None

        if self.ec_data.conditions.get("icon_code", {}).get("value"):
            icon_code = self.ec_data.conditions["icon_code"]["value"]
        elif self.ec_data.hourly_forecasts and self.ec_data.hourly_forecasts[0].get(
            "icon_code"
        ):
            icon_code = self.ec_data.hourly_forecasts[0]["icon_code"]

        if icon_code:
            return icon_code_to_condition(int(icon_code))
        return ""

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return get_forecast(self.ec_data, False)

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return get_forecast(self.ec_data, True)

    def _async_environment_canada_forecasts(self) -> ServiceResponse:
        """Return the native Environment Canada forecast."""
        daily = []
        for f in self.ec_data.daily_forecasts:
            day = f.copy()
            day["timestamp"] = day["timestamp"].isoformat()
            daily.append(day)

        hourly = []
        for f in self.ec_data.hourly_forecasts:
            hour = f.copy()
            hour["timestamp"] = hour["period"].isoformat()
            del hour["period"]
            hourly.append(hour)

        return {"daily_forecast": daily, "hourly_forecast": hourly}


def get_forecast(ec_data, hourly) -> list[Forecast] | None:
    """Build the forecast array."""
    forecast_array: list[Forecast] = []

    if not hourly:
        if not (half_days := ec_data.daily_forecasts):
            return None

        def get_day_forecast(
            fcst: list[dict[str, Any]],
        ) -> Forecast:
            high_temp = int(fcst[0]["temperature"]) if len(fcst) == 2 else None
            return {
                ATTR_FORECAST_TIME: fcst[0]["timestamp"].isoformat(),
                ATTR_FORECAST_NATIVE_TEMP: high_temp,
                ATTR_FORECAST_NATIVE_TEMP_LOW: int(fcst[-1]["temperature"]),
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                    fcst[0]["precip_probability"]
                ),
                ATTR_FORECAST_CONDITION: icon_code_to_condition(
                    int(fcst[0]["icon_code"])
                ),
            }

        i = 2 if half_days[0]["temperature_class"] == "high" else 1
        forecast_array.append(get_day_forecast(half_days[0:i]))
        for i in range(i, len(half_days) - 1, 2):
            forecast_array.append(get_day_forecast(half_days[i : i + 2]))  # noqa: PERF401

    else:
        forecast_array.extend(
            {
                ATTR_FORECAST_TIME: hour["period"].isoformat(),
                ATTR_FORECAST_NATIVE_TEMP: int(hour["temperature"]),
                ATTR_FORECAST_CONDITION: icon_code_to_condition(int(hour["icon_code"])),
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: int(
                    hour["precip_probability"]
                ),
            }
            for hour in ec_data.hourly_forecasts
        )

    return forecast_array


def icon_code_to_condition(icon_code):
    """Return the condition corresponding to an icon code."""
    for condition, codes in ICON_CONDITION_MAP.items():
        if icon_code in codes:
            return condition
    return None
