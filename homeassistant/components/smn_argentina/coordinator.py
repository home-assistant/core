"""DataUpdateCoordinator for the SMN integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from smn_argentina_api import SMNApiClient, SMNTokenManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ArgentinaSMNData:
    """Class to handle SMN data."""

    def __init__(
        self,
        api_client: SMNApiClient,
        latitude: float,
        longitude: float,
        location_id: str | None = None,
    ) -> None:
        """Initialize the data object."""
        self._api_client = api_client
        self._latitude = latitude
        self._longitude = longitude
        self._location_id = location_id

        self.current_weather_data: dict[str, Any] = {}
        self.daily_forecast: list[dict[str, Any]] = []
        self.hourly_forecast: list[dict[str, Any]] = []
        self.alerts: dict[str, Any] = {}
        self.shortterm_alerts: list[dict[str, Any]] = []
        self.heat_warnings: dict[str, Any] = {}

    async def _get_location_id(self) -> str:
        """Get the location ID from coordinates."""
        if self._location_id:
            return self._location_id

        data = await self._api_client.async_get_location(
            self._latitude, self._longitude
        )

        # Extract location ID from response
        if isinstance(data, dict):
            self._location_id = str(data.get("id") or data.get("location_id"))
        elif isinstance(data, list) and len(data) > 0:
            self._location_id = str(data[0].get("id") or data[0].get("location_id"))
        else:
            raise UpdateFailed(f"Unexpected response format: {data}")

        _LOGGER.debug(
            "Location ID for %s,%s: %s",
            self._latitude,
            self._longitude,
            self._location_id,
        )
        return self._location_id

    @property
    def location_id(self) -> str | None:
        """Return the location ID."""
        return self._location_id

    async def fetch_data(self) -> None:
        """Fetch data from SMN API."""
        try:
            location_id = await self._get_location_id()

            await self._fetch_current_weather(location_id)
            await self._fetch_forecast(location_id)
            await self._fetch_alerts(location_id)
            await self._fetch_shortterm_alerts(location_id)

        except Exception as err:
            raise UpdateFailed(f"Error fetching SMN data: {err}") from err

    async def _fetch_current_weather(self, location_id: str) -> None:
        """Fetch current weather data."""
        data = await self._api_client.async_get_current_weather(location_id)

        if isinstance(data, dict):
            wind_data = data.get("wind", {})
            location_data = data.get("location", {})

            self.current_weather_data = {
                "temperature": data.get("temperature"),
                "feels_like": data.get("feels_like"),
                "humidity": data.get("humidity"),
                "pressure": data.get("pressure"),
                "visibility": data.get("visibility"),
                "wind_speed": wind_data.get("speed")
                if isinstance(wind_data, dict)
                else None,
                "wind_deg": wind_data.get("deg")
                if isinstance(wind_data, dict)
                else None,
                "weather": data.get("weather"),
                "name": location_data.get("name")
                if isinstance(location_data, dict)
                else None,
            }
            _LOGGER.debug(
                "Updated current weather data for location %s: temp=%s, feels_like=%s",
                location_id,
                self.current_weather_data.get("temperature"),
                self.current_weather_data.get("feels_like"),
            )

    async def _fetch_forecast(self, location_id: str) -> None:
        """Fetch forecast data."""
        data = await self._api_client.async_get_forecast(location_id)

        # Parse forecast data structure
        forecast_data = data.get("forecast", []) if isinstance(data, dict) else data

        if isinstance(forecast_data, list):
            # Store daily forecast data
            self.daily_forecast = []
            self.hourly_forecast = []

            for day in forecast_data:
                # Get representative weather condition from afternoon period
                afternoon = day.get("afternoon", {})
                weather_obj = (
                    afternoon.get("weather") if isinstance(afternoon, dict) else None
                )

                # Create daily forecast entry - store full weather object to preserve ID
                daily_entry = {
                    "date": day.get("date"),
                    "temp_max": day.get("temp_max"),
                    "temp_min": day.get("temp_min"),
                    "weather": weather_obj,  # Store full object with id and description
                }
                self.daily_forecast.append(daily_entry)

                # Create hourly forecasts from time periods
                periods = [
                    ("early_morning", "03:00"),
                    ("morning", "09:00"),
                    ("afternoon", "15:00"),
                    ("night", "21:00"),
                ]

                for period_name, period_time in periods:
                    period_data = day.get(period_name)
                    if period_data and isinstance(period_data, dict):
                        # Extract wind data
                        wind_data = period_data.get("wind", {})
                        # Use average of speed_range if available
                        speed_range = (
                            wind_data.get("speed_range", [])
                            if isinstance(wind_data, dict)
                            else []
                        )
                        wind_speed = (
                            sum(speed_range) / len(speed_range)
                            if speed_range
                            else wind_data.get("speed")
                            if isinstance(wind_data, dict)
                            else None
                        )

                        # Store full weather object to preserve ID
                        weather_obj = period_data.get("weather")

                        hourly_entry = {
                            "date": day.get("date"),
                            "time": period_time,
                            "datetime": f"{day.get('date')}T{period_time}:00",
                            "temperature": period_data.get("temperature"),
                            "weather": weather_obj,
                            "humidity": period_data.get("humidity"),
                            "wind_speed": wind_speed,
                            "wind_direction": (
                                wind_data.get("deg")
                                if isinstance(wind_data, dict)
                                else None
                            ),
                        }
                        self.hourly_forecast.append(hourly_entry)

            _LOGGER.debug(
                "Parsed %d daily forecasts and %d hourly forecasts",
                len(self.daily_forecast),
                len(self.hourly_forecast),
            )

    async def _fetch_alerts(self, location_id: str) -> None:
        """Fetch weather alerts."""
        data = await self._api_client.async_get_alerts(location_id)

        # Store full alerts data (dict with warnings, reports, area_id)
        self.alerts = data

        # Get area_id for heat warnings if available
        area_id = data.get("area_id")
        if area_id:
            await self._fetch_heat_warnings(area_id)

    async def _fetch_shortterm_alerts(self, location_id: str) -> None:
        """Fetch short-term severe weather alerts."""
        self.shortterm_alerts = await self._api_client.async_get_shortterm_alerts(
            location_id
        )

    async def _fetch_heat_warnings(self, area_id: str) -> None:
        """Fetch heat warnings."""
        self.heat_warnings = await self._api_client.async_get_heat_warnings(area_id)


class ArgentinaSMNDataUpdateCoordinator(DataUpdateCoordinator[ArgentinaSMNData]):
    """Class to manage fetching SMN data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self._token_refresh_unsub: Callable[[], None] | None = None

        # Get coordinates from config entry
        latitude = config_entry.data[CONF_LATITUDE]
        longitude = config_entry.data[CONF_LONGITUDE]

        # Create API client
        session = async_get_clientsession(hass)
        token_manager = SMNTokenManager(session)
        api_client = SMNApiClient(session, token_manager)

        # Store token manager for refresh scheduling
        self._token_manager = token_manager

        # Store data handler before calling super().__init__
        self._smn_data = ArgentinaSMNData(api_client, latitude, longitude)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> ArgentinaSMNData:
        """Fetch data from API."""
        await self._smn_data.fetch_data()

        # Schedule token refresh if needed
        self._schedule_token_refresh()

        return self._smn_data

    def _schedule_token_refresh(self) -> None:
        """Schedule token refresh before expiration."""
        # Cancel existing refresh if any
        if self._token_refresh_unsub:
            self._token_refresh_unsub()
            self._token_refresh_unsub = None

        # Get token expiration
        expiration = self._token_manager.token_expiration
        if not expiration:
            return

        # Schedule refresh 5 minutes before expiration
        now = dt_util.utcnow()
        refresh_time = expiration - timedelta(minutes=5)

        if refresh_time <= now:
            # Token expires very soon, will be refreshed on next data fetch
            return

        # Calculate seconds until refresh
        seconds_until_refresh = (refresh_time - now).total_seconds()

        _LOGGER.debug(
            "Scheduling token refresh in %.0f seconds (at %s)",
            seconds_until_refresh,
            refresh_time.isoformat(),
        )

        async def _refresh_token(now):
            """Refresh token callback."""
            try:
                await self._token_manager.fetch_token()
                _LOGGER.debug("Token refreshed successfully")
                # Schedule next refresh
                self._schedule_token_refresh()
            except UpdateFailed as err:
                _LOGGER.error("Failed to refresh token: %s", err)
            except Exception:
                _LOGGER.exception("Unexpected error refreshing token")

        self._token_refresh_unsub = async_call_later(
            self.hass, seconds_until_refresh, _refresh_token
        )
