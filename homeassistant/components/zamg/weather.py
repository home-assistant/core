"""Sensor for the zamg integration."""

from datetime import datetime
from typing import override

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
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
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sun import is_up
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, CONF_STATION_ID, DOMAIN, MANUFACTURER_URL
from .coordinator import ZamgConfigEntry, ZamgDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZamgConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ZAMG weather platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        [ZamgWeather(coordinator, entry.title, entry.data[CONF_STATION_ID])]
    )


class ZamgWeather(CoordinatorEntity, WeatherEntity):
    """Representation of a weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    def __init__(
        self, coordinator: ZamgDataUpdateCoordinator, name: str, station_id: str
    ) -> None:
        """Initialise the platform with a data instance and station name."""
        super().__init__(coordinator)
        self._attr_unique_id = station_id
        self._attr_name = name
        self.station_id = f"{station_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, station_id)},
            manufacturer=ATTRIBUTION,
            configuration_url=MANUFACTURER_URL,
            name=name,
        )

    def _condition(self, sy: int, date_time: datetime | None = None) -> str:
        """Return the weather condition based on the Geosphere symbol code."""
        if sy in (1, 2):
            if self._is_night(date_time):
                return ATTR_CONDITION_CLEAR_NIGHT
            return ATTR_CONDITION_SUNNY
        if sy == 3:
            return ATTR_CONDITION_PARTLYCLOUDY
        if sy in (4, 5):
            return ATTR_CONDITION_CLOUDY
        if sy in (6, 7):
            return ATTR_CONDITION_FOG
        if sy in (8, 9):
            return ATTR_CONDITION_RAINY
        if sy == 10:
            return ATTR_CONDITION_POURING
        if sy in (11, 12, 13, 20, 21, 22):
            return ATTR_CONDITION_SNOWY_RAINY
        if sy in (14, 15, 16, 23, 24, 25):
            return ATTR_CONDITION_SNOWY
        if sy in (17, 18):
            return ATTR_CONDITION_RAINY
        if sy == 19:
            return ATTR_CONDITION_POURING
        if sy in (26, 27, 28):
            return ATTR_CONDITION_LIGHTNING
        if sy in (29, 30, 31, 32):
            return ATTR_CONDITION_LIGHTNING_RAINY
        return ATTR_CONDITION_EXCEPTIONAL

    def _is_night(self, date_time: datetime | None = None) -> bool:
        """Return whether the given time is at night."""
        date_time = date_time or dt_util.now()
        if self.hass is None:
            return date_time.hour < 6 or date_time.hour >= 18
        return not is_up(self.hass, date_time)

    def _as_datetime(self, timestamp: str | datetime) -> datetime:
        """Normalize timestamp values to datetime."""
        if isinstance(timestamp, datetime):
            return dt_util.as_local(timestamp)
        parsed_timestamp = dt_util.parse_datetime(timestamp, raise_on_error=True)
        return dt_util.as_local(parsed_timestamp)

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        try:
            forecast_data = self.coordinator.data["nowcast"]
            sy = int(forecast_data.get("sy"))
            return self._condition(sy, dt_util.now())
        except KeyError, ValueError, TypeError:
            return None

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        try:
            return float(self.coordinator.data["nowcast"]["t2m"])
        except KeyError, ValueError, TypeError:
            return None

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        try:
            return float(self.coordinator.data[self.station_id]["P"]["data"])
        except KeyError, ValueError, TypeError:
            return None

    @property
    @override
    def humidity(self) -> float | None:
        """Return the humidity."""
        try:
            return float(self.coordinator.data["nowcast"]["rh2m"])
        except KeyError, ValueError, TypeError:
            return None

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        try:
            return float(self.coordinator.data["nowcast"]["wind_speed"])
        except KeyError, ValueError, TypeError:
            return None

    @property
    @override
    def wind_bearing(self) -> float | None:
        """Return the wind bearing."""
        try:
            if (
                value := self.coordinator.data[self.station_id]["DD"]["data"]
            ) is not None:
                return float(value)
            if (
                value := self.coordinator.data[self.station_id]["DDX"]["data"]
            ) is not None:
                return float(value)
        except KeyError, ValueError, TypeError:
            return None
        return None

    @override
    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        try:
            forecast_data = self.coordinator.data["forecast"]
            features = forecast_data.get("features")
            timestamps = forecast_data.get("timestamps")
            if not features or not timestamps:
                return None
            feature = features[0].get("properties", {}).get("parameters", {})
            forecast_dict = {
                "timestamps": timestamps,
                "t2m": feature.get("t2m", {}).get("data"),
                "rain": feature.get("rain", {}).get("data"),
                "wind_speed": feature.get("wind_speed", {}).get("data"),
                "rh2m": feature.get("rh2m", {}).get("data"),
                "sy": [
                    int(x) if x is not None else None
                    for x in feature.get("sy", {}).get("data", [])
                ],
            }
            # get index of first timestamp that is greater than now
            dt_now = dt_util.now()
            start_index = 0
            for i, timestamp in enumerate(forecast_dict["timestamps"]):
                if self._as_datetime(timestamp) > dt_now:
                    start_index = i
                    break
            forecast_data = {
                key: value[start_index:] if value else []
                for key, value in forecast_dict.items()
            }
            # go through the forecast data and create a list of Forecast objects
            hourly_forecast = []
            for i, timestamp in enumerate(forecast_data["timestamps"]):
                forecast_datetime = self._as_datetime(timestamp)
                hourly_forecast.append(
                    Forecast(
                        datetime=forecast_datetime.replace(tzinfo=None).isoformat(),
                        condition=self._condition(
                            sy=forecast_data["sy"][i],
                            date_time=forecast_datetime,
                        ),
                        native_precipitation=forecast_data["rain"][i],
                        native_temperature=forecast_data["t2m"][i],
                        native_wind_speed=forecast_data["wind_speed"][i],
                        humidity=forecast_data["rh2m"][i],
                    )
                )
        except KeyError, ValueError, TypeError:
            return None
        else:
            return hourly_forecast
