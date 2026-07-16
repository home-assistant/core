"""Sensor for the zamg integration."""

from datetime import datetime
from typing import override

from homeassistant.components.weather import (
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import naive_now

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

    def _is_night(self, date_time: datetime | None = None) -> bool:
        """Check if it is currently night time."""
        if date_time is None:
            date_time = naive_now()
        hour = date_time.hour
        return hour < 6 or hour >= 18

    def _condition(
        self, tcc: float, rain: float, date_time: datetime | None = None
    ) -> str:
        """Determine the weather condition based on tcc and rain."""
        if rain > 0.2:
            return "rainy"
        if tcc <= 20:
            return "clear-night" if self._is_night(date_time) else "sunny"
        if tcc <= 50:
            return "partlycloudy"
        if tcc <= 80:
            return "cloudy"
        return "fog"

    def _as_datetime(self, timestamp: str | datetime) -> datetime:
        """Normalize timestamp values to datetime."""
        if isinstance(timestamp, datetime):
            return timestamp
        return datetime.fromisoformat(timestamp)

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        try:
            forecast_data = self.coordinator.data["nowcast"]
            tcc = forecast_data.get("tcc")
            rain = forecast_data.get("rain")
            return self._condition(tcc, rain, naive_now())
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
                "tcc": feature.get("tcc", {}).get("data"),
            }
            # get index of first timestamp that is greater than now
            now = naive_now()
            start_index = 0
            for i, timestamp in enumerate(forecast_dict["timestamps"]):
                if self._as_datetime(timestamp) > now:
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
                        datetime=forecast_datetime.isoformat(),
                        condition=self._condition(
                            tcc=forecast_data["tcc"][i],
                            rain=forecast_data["rain"][i],
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
