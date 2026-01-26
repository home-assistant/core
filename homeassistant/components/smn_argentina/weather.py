"""Weather platform for SMN."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
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

from .const import ATTR_MAP, CONDITION_ID_MAP, DOMAIN
from .coordinator import ArgentinaSMNDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def format_condition(condition: dict | None, sun_is_up: bool = True) -> str:
    """Map SMN weather condition ID to HA condition.

    Condition MUST be a dict with an 'id' field from the SMN API.
    Only ID-based mapping is used for accuracy.
    """
    # Handle None or missing condition
    if not condition or not isinstance(condition, dict):
        _LOGGER.debug("format_condition: No valid condition dict, returning default")
        return ATTR_CONDITION_SUNNY if sun_is_up else ATTR_CONDITION_CLEAR_NIGHT

    # Get weather ID (required)
    weather_id = condition.get("id")
    if weather_id is None:
        _LOGGER.debug("format_condition: Weather dict has no 'id' field: %s", condition)
        return ATTR_CONDITION_SUNNY if sun_is_up else ATTR_CONDITION_CLEAR_NIGHT

    # Map ID to HA condition
    ha_condition = CONDITION_ID_MAP.get(weather_id)
    if not ha_condition:
        _LOGGER.debug("format_condition: Unknown weather ID: %s", weather_id)
        return ATTR_CONDITION_SUNNY if sun_is_up else ATTR_CONDITION_CLEAR_NIGHT

    # Special handling: Current weather endpoint uses day IDs even at night
    # Convert sunny (ID 3) to clear-night if sun is down
    if ha_condition == ATTR_CONDITION_SUNNY and not sun_is_up:
        _LOGGER.debug(
            "format_condition: Converted ID %s from sunny to clear-night (sun down)",
            weather_id,
        )
        return ATTR_CONDITION_CLEAR_NIGHT

    _LOGGER.debug("format_condition: Mapped ID %s to %s", weather_id, ha_condition)
    return ha_condition


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry[ArgentinaSMNDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMN weather based on a config entry."""
    coordinator: ArgentinaSMNDataUpdateCoordinator = config_entry.runtime_data

    async_add_entities([SMNWeather(coordinator, config_entry)])


class SMNWeather(CoordinatorEntity[ArgentinaSMNDataUpdateCoordinator], WeatherEntity):
    """Implementation of an SMN weather entity."""

    _attr_attribution = (
        "Data provided by Servicio Meteorológico Nacional de Argentina (SMN)"
    )
    _attr_has_entity_name = True
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        coordinator: ArgentinaSMNDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_name = None
        self._attr_unique_id = f"{config_entry.entry_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        location_id = self.coordinator.data.location_id
        device_info_dict = {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": self._config_entry.data.get(CONF_NAME, "SMN Weather"),
            "manufacturer": "Servicio Meteorológico Nacional de Argentina (SMN)",
            "entry_type": DeviceEntryType.SERVICE,
        }

        # Add location_id to configuration_url if available
        if location_id:
            device_info_dict["configuration_url"] = (
                f"https://www.smn.gob.ar/pronostico/?loc={location_id}"
            )

        return DeviceInfo(**device_info_dict)  # type: ignore[typeddict-item]

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if not self.coordinator.data.current_weather_data:
            return None

        # Try description first, then weather
        condition = self.coordinator.data.current_weather_data.get(
            "description"
        ) or self.coordinator.data.current_weather_data.get("weather")

        sun_up = is_up(self.hass)
        return format_condition(condition, sun_up)

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.current_weather_data.get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature (feels like)."""
        return self.coordinator.data.current_weather_data.get("feels_like")

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.coordinator.data.current_weather_data.get("humidity")

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self.coordinator.data.current_weather_data.get("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.data.current_weather_data.get("wind_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self.coordinator.data.current_weather_data.get("wind_deg")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self.coordinator.data.current_weather_data.get(
            ATTR_MAP.get("visibility", "visibility")
        )

    def _format_forecast(
        self, forecast_data: list[dict[str, Any]], is_daily: bool = False
    ) -> list[Forecast]:
        """Format forecast data for Home Assistant."""
        if not forecast_data:
            return []

        forecasts: list[Forecast] = []

        for item in forecast_data:
            # Skip if missing required fields
            if not item.get("date") and not item.get("datetime"):
                continue

            if is_daily:
                # Daily forecast has temp_max and temp_min
                weather_obj = item.get("weather")
                _LOGGER.debug(
                    "Daily forecast for %s - weather: %s", item.get("date"), weather_obj
                )
                forecast = Forecast(
                    datetime=self._parse_datetime(item.get("date")),  # type: ignore[typeddict-item]
                    native_temperature=item.get("temp_max"),
                    native_templow=item.get("temp_min"),
                    condition=format_condition(weather_obj),
                )
            else:
                # Hourly forecast has individual period data
                weather_obj = item.get("weather")
                _LOGGER.debug(
                    "Hourly forecast for %s - weather: %s",
                    item.get("datetime"),
                    weather_obj,
                )
                forecast = Forecast(
                    datetime=self._parse_datetime(item.get("datetime")),  # type: ignore[typeddict-item]
                    native_temperature=item.get("temperature"),
                    condition=format_condition(weather_obj),
                    humidity=item.get("humidity"),
                    native_wind_speed=item.get("wind_speed"),
                    wind_bearing=item.get("wind_direction"),
                )

            forecasts.append(forecast)

        return forecasts

    def _parse_datetime(self, date_str: str | None) -> str | None:
        """Parse datetime string to ISO format."""
        if not date_str:
            return None

        try:
            # Try parsing as ISO format
            if dt := dt_util.parse_datetime(date_str):
                return dt.isoformat()

            # Try parsing as date only
            if date_obj := dt_util.parse_date(date_str):
                return datetime.combine(date_obj, datetime.min.time()).isoformat()
        except (ValueError, TypeError):
            pass

        return date_str

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        return self._format_forecast(
            self.coordinator.data.daily_forecast, is_daily=True
        )

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        return self._format_forecast(
            self.coordinator.data.hourly_forecast, is_daily=False
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {}

        # Add alerts if available
        if self.coordinator.data.alerts:
            attrs["alerts"] = self.coordinator.data.alerts

        # Add heat warnings if available
        if self.coordinator.data.heat_warnings:
            attrs["heat_warnings"] = self.coordinator.data.heat_warnings

        return attrs
