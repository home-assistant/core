"""Support for Buienradar.nl weather service."""

from typing import override

from buienradar.constants import (
    CONDCODE,
    CONDITION,
    DATETIME,
    MAX_TEMP,
    MIN_TEMP,
    NIGHTTIME,
    RAIN,
    RAIN_CHANCE,
    WINDAZIMUTH,
    WINDSPEED,
)

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
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BuienRadarConfigEntry, BuienradarCoordinator
from .util import BuienradarData

CONF_FORECAST = "forecast"

DATA_CONDITION = "buienradar_condition"

CONDITION_CLASSES = {
    ATTR_CONDITION_CLOUDY: ("c", "p"),
    ATTR_CONDITION_FOG: ("d", "n"),
    ATTR_CONDITION_HAIL: (),
    ATTR_CONDITION_LIGHTNING: ("g",),
    ATTR_CONDITION_LIGHTNING_RAINY: ("s",),
    ATTR_CONDITION_PARTLYCLOUDY: (
        "b",
        "j",
        "o",
        "r",
    ),
    ATTR_CONDITION_POURING: ("l", "q"),
    ATTR_CONDITION_RAINY: ("f", "h", "k", "m"),
    ATTR_CONDITION_SNOWY: ("u", "i", "v", "t"),
    ATTR_CONDITION_SNOWY_RAINY: ("w",),
    ATTR_CONDITION_SUNNY: ("a",),
    ATTR_CONDITION_WINDY: (),
    ATTR_CONDITION_WINDY_VARIANT: (),
    ATTR_CONDITION_EXCEPTIONAL: (),
}
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BuienRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buienradar platform."""
    async_add_entities([BrWeather(entry.runtime_data, entry.data)])


class BrWeather(CoordinatorEntity[BuienradarCoordinator], WeatherEntity):
    """Representation of a weather condition."""

    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_visibility_unit = UnitOfLength.METERS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

    def __init__(self, coordinator: BuienradarCoordinator, config) -> None:
        """Initialize the platform with a data instance and station name."""
        super().__init__(coordinator)
        coordinates = coordinator.coordinates
        self._stationname = config.get(CONF_NAME, "Buienradar")
        self._attr_name = self._stationname or f"BR {'(unknown station)'}"

        self._attr_unique_id = (
            f"{coordinates[CONF_LATITUDE]:2.6f}{coordinates[CONF_LONGITUDE]:2.6f}"
        )
        self._forecast: list | None = None
        self._update_from_data()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_data()
        super()._handle_coordinator_update()
        self.coordinator.config_entry.async_create_task(
            self.hass, self.async_update_listeners(("daily",))
        )

    def _update_from_data(self) -> None:
        """Update the attributes from the coordinator data."""
        data = self.coordinator.data
        self._attr_attribution = data.attribution
        self._attr_condition = self._calc_condition(data)
        self._forecast = self._calc_forecast(data)
        self._attr_humidity = data.humidity
        self._attr_name = (
            self._stationname or f"BR {data.stationname or '(unknown station)'}"
        )
        self._attr_native_pressure = data.pressure
        self._attr_native_temperature = data.temperature
        self._attr_native_apparent_temperature = data.feeltemperature
        self._attr_native_visibility = data.visibility
        self._attr_native_wind_gust_speed = data.wind_gust
        self._attr_native_wind_speed = data.wind_speed
        self._attr_wind_bearing = data.wind_bearing

    def _calc_condition(self, data: BuienradarData):
        """Return the current condition."""
        if data.condition and (ccode := data.condition.get(CONDCODE)):
            condition = CONDITION_MAP.get(ccode)
            if condition == ATTR_CONDITION_SUNNY and data.condition.get(NIGHTTIME):
                return ATTR_CONDITION_CLEAR_NIGHT
            return condition
        return None

    def _calc_forecast(self, data: BuienradarData):
        """Return the forecast array."""
        fcdata_out = []

        if not data.forecast:
            return None

        for data_in in data.forecast:
            # remap keys from external library to
            # keys understood by the weather component:
            condcode = data_in.get(CONDITION, {}).get(CONDCODE)
            data_out = {
                ATTR_FORECAST_TIME: data_in.get(DATETIME).isoformat(),
                ATTR_FORECAST_CONDITION: CONDITION_MAP.get(condcode),
                ATTR_FORECAST_NATIVE_TEMP_LOW: data_in.get(MIN_TEMP),
                ATTR_FORECAST_NATIVE_TEMP: data_in.get(MAX_TEMP),
                ATTR_FORECAST_NATIVE_PRECIPITATION: data_in.get(RAIN),
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: data_in.get(RAIN_CHANCE),
                ATTR_FORECAST_WIND_BEARING: data_in.get(WINDAZIMUTH),
                ATTR_FORECAST_NATIVE_WIND_SPEED: data_in.get(WINDSPEED),
            }

            fcdata_out.append(data_out)

        return fcdata_out

    @override
    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return self._forecast
