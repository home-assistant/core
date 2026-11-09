"""Weather platform for the GeoSphere Austria Forecast integration."""

from datetime import datetime, timedelta
import math
from typing import override

from zamg import NwpForecastRecord, symbol_to_condition

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.util import dt as dt_util

from .coordinator import (
    GeoSphereAustriaForecastConfigEntry,
    GeoSphereAustriaForecastCoordinator,
)

PARALLEL_UPDATES = 0

# Interval values such as precipitation are reported for the hour that ends at
# the record's time, so the record for "now" is the first one after it.
_RECORD_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeoSphereAustriaForecastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a weather entity for every configured location."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [GeoSphereAustriaForecastWeather(coordinator, subentry_id)],
            config_subentry_id=subentry_id,
        )


def _current_record(
    records: tuple[NwpForecastRecord, ...], now: datetime
) -> NwpForecastRecord | None:
    """Return the record whose hour contains the given time."""
    return next(
        (
            record
            for record in records
            if record.valid_time - _RECORD_INTERVAL <= now < record.valid_time
        ),
        None,
    )


def _wind(record: NwpForecastRecord) -> tuple[float | None, float | None]:
    """Return the wind speed and the direction the wind comes from."""
    if record.wind_u is None or record.wind_v is None:
        return None, None
    speed = math.hypot(record.wind_u, record.wind_v)
    if speed == 0:
        return speed, None
    # The components point where the wind blows to; the bearing is where it
    # comes from, measured clockwise from north.
    return speed, round(
        math.degrees(math.atan2(-record.wind_u, -record.wind_v)), 1
    ) % 360


def _to_forecast(record: NwpForecastRecord) -> Forecast:
    """Convert a forecast record to a Home Assistant forecast."""
    wind_speed, wind_bearing = _wind(record)
    return Forecast(
        datetime=record.valid_time.isoformat(),
        condition=symbol_to_condition(record.symbol),
        native_temperature=record.temperature,
        humidity=record.relative_humidity,
        cloud_coverage=record.cloud_cover,
        native_precipitation=record.precipitation,
        native_pressure=record.mean_sea_level_pressure,
        native_wind_speed=wind_speed,
        wind_bearing=wind_bearing,
        native_wind_gust_speed=record.wind_gust,
    )


class GeoSphereAustriaForecastWeather(
    SingleCoordinatorWeatherEntity[GeoSphereAustriaForecastCoordinator]
):
    """Weather entity for one GeoSphere Austria Forecast location."""

    _attr_attribution = "Data provided by GeoSphere Austria"
    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.PA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    def __init__(
        self, coordinator: GeoSphereAustriaForecastCoordinator, subentry_id: str
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._attr_unique_id = subentry_id
        self._attr_device_info = coordinator.device_info

    @override
    async def async_added_to_hass(self) -> None:
        """Switch to the next record at every full hour."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_utc_time_change(
                self.hass, self._async_hour_changed, minute=0, second=0
            )
        )

    @callback
    def _async_hour_changed(self, now: datetime) -> None:
        """Update the state and the forecast for the new hour."""
        self._handle_coordinator_update()

    @property
    def _record(self) -> NwpForecastRecord | None:
        """Return the record for the current hour."""
        return _current_record(self.coordinator.data.records, dt_util.utcnow())

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        if (record := self._record) is None:
            return None
        return symbol_to_condition(record.symbol)

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        if (record := self._record) is None:
            return None
        return record.temperature

    @property
    @override
    def humidity(self) -> float | None:
        """Return the humidity."""
        if (record := self._record) is None:
            return None
        return record.relative_humidity

    @property
    @override
    def cloud_coverage(self) -> float | None:
        """Return the cloud coverage."""
        if (record := self._record) is None:
            return None
        return record.cloud_cover

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return the mean sea level pressure."""
        if (record := self._record) is None:
            return None
        return record.mean_sea_level_pressure

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        if (record := self._record) is None:
            return None
        return _wind(record)[0]

    @property
    @override
    def wind_bearing(self) -> float | None:
        """Return the direction the wind comes from."""
        if (record := self._record) is None:
            return None
        return _wind(record)[1]

    @property
    @override
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        if (record := self._record) is None:
            return None
        return record.wind_gust

    @callback
    @override
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast from the current hour on."""
        now = dt_util.utcnow()
        return [
            _to_forecast(record)
            for record in self.coordinator.data.records
            if record.valid_time > now
        ]
