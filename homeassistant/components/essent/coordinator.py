"""DataUpdateCoordinator for Essent integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from http import HTTPStatus
import logging
import random
from typing import Any, TypedDict

from aiohttp import ClientError, ClientTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import API_ENDPOINT, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)
CLIENT_TIMEOUT = ClientTimeout(total=10)


class EssentEnergyData(TypedDict):
    """Data for a single Essent energy type."""

    tariffs: list[dict[str, Any]]
    tariffs_tomorrow: list[dict[str, Any]]
    unit: str
    min_price: float
    avg_price: float
    max_price: float


type EssentData = dict[str, EssentEnergyData]
type EssentConfigEntry = ConfigEntry["EssentDataUpdateCoordinator"]


def _tariff_sort_key(tariff: dict[str, Any]) -> str:
    """Sort key for tariffs based on start time."""
    return tariff.get("startDateTime", "")


def _normalize_unit(unit: str) -> str:
    """Normalize unit strings to HA's canonical constants."""
    unit_normalized = unit.replace("³", "3").lower()
    if unit_normalized == "kwh":
        return UnitOfEnergy.KILO_WATT_HOUR
    if unit_normalized in {"m3", "m^3"}:
        return UnitOfVolume.CUBIC_METERS
    return unit


class EssentDataUpdateCoordinator(DataUpdateCoordinator[EssentData]):
    """Class to manage fetching Essent data."""

    config_entry: EssentConfigEntry | None

    def __init__(
        self, hass: HomeAssistant, config_entry: EssentConfigEntry | None = None
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=None,  # explicit scheduling
        )
        self._unsub_data: Callable[[], None] | None = None
        self._unsub_listener: Callable[[], None] | None = None
        # Random minute offset for API fetches (0-59 minutes)
        self._api_fetch_minute_offset = random.randint(0, 59)

    @property
    def api_fetch_minute_offset(self) -> int:
        """Return the configured minute offset for API fetches."""
        return self._api_fetch_minute_offset

    @property
    def api_refresh_scheduled(self) -> bool:
        """Return whether the API refresh task is scheduled."""
        return self._unsub_data is not None

    @property
    def listener_tick_scheduled(self) -> bool:
        """Return whether the listener tick task is scheduled."""
        return self._unsub_listener is not None

    def start_schedules(self) -> None:
        """Start both API fetch and listener tick schedules.

        This should be called after the first successful data fetch.
        Schedules will continue running regardless of API success/failure.
        """
        if self.config_entry and self.config_entry.pref_disable_polling:
            _LOGGER.debug("Polling disabled by config entry, not starting schedules")
            return

        if self._unsub_data or self._unsub_listener:
            return

        _LOGGER.info(
            "Starting schedules: API fetch every hour at minute %d, "
            "listener updates on the hour",
            self._api_fetch_minute_offset,
        )
        self._schedule_data_refresh()
        self._schedule_listener_tick()

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        await super().async_shutdown()
        if self._unsub_data:
            self._unsub_data()
            self._unsub_data = None
        if self._unsub_listener:
            self._unsub_listener()
            self._unsub_listener = None

    def _schedule_data_refresh(self) -> None:
        """Schedule next data fetch at a random minute offset within the hour."""
        if self._unsub_data:
            self._unsub_data()

        now = dt_util.utcnow()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        candidate = current_hour + UPDATE_INTERVAL + timedelta(
            minutes=self._api_fetch_minute_offset
        )
        if candidate <= now:
            candidate = candidate + UPDATE_INTERVAL

        _LOGGER.debug(
            "Scheduling next API fetch for %s (offset: %d minutes)",
            candidate,
            self._api_fetch_minute_offset,
        )

        @callback
        def _handle(_: datetime) -> None:
            """Handle the scheduled API refresh trigger."""
            self._unsub_data = None
            self.hass.async_create_task(self.async_request_refresh())
            # Reschedule for next hour regardless of success/failure
            self._schedule_data_refresh()

        self._unsub_data = async_track_point_in_utc_time(self.hass, _handle, candidate)

    def _schedule_listener_tick(self) -> None:
        """Schedule listener updates on the hour to advance cached tariffs."""
        if self._unsub_listener:
            self._unsub_listener()

        now = dt_util.utcnow()
        next_hour = now + UPDATE_INTERVAL
        next_run = datetime(
            next_hour.year,
            next_hour.month,
            next_hour.day,
            next_hour.hour,
            tzinfo=dt_util.UTC,
        )

        _LOGGER.debug("Scheduling next listener tick for %s", next_run)

        @callback
        def _handle(_: datetime) -> None:
            """Handle the scheduled listener tick to update sensors."""
            self._unsub_listener = None
            _LOGGER.debug("Listener tick fired, updating sensors with cached data")
            self.async_update_listeners()
            self._schedule_listener_tick()

        self._unsub_listener = async_track_point_in_utc_time(
            self.hass,
            _handle,
            next_run,
        )

    def _normalize_energy_block(
        self,
        data: dict[str, Any],
        energy_type: str,
        tomorrow: dict[str, Any] | None,
    ) -> EssentEnergyData:
        """Normalize the energy block into the coordinator format."""
        tariffs_today = sorted(
            data.get("tariffs", []),
            key=_tariff_sort_key,
        )
        if not tariffs_today:
            _LOGGER.debug("No tariffs found for %s in payload: %s", energy_type, data)
            raise UpdateFailed(f"No tariffs found for {energy_type}")

        tariffs_tomorrow: list[dict[str, Any]] = []
        if tomorrow:
            tariffs_tomorrow = sorted(
                tomorrow.get("tariffs", []),
                key=_tariff_sort_key,
            )
        unit = (data.get("unitOfMeasurement") or data.get("unit") or "").strip()

        amounts = [
            float(total)
            for tariff in tariffs_today
            if (total := tariff.get("totalAmount")) is not None
        ]
        if not amounts:
            _LOGGER.debug(
                "No usable totalAmount values for %s in tariffs: %s",
                energy_type,
                tariffs_today,
            )
            raise UpdateFailed(f"No usable tariff values for {energy_type}")

        if not unit:
            _LOGGER.debug("No unit provided for %s in payload: %s", energy_type, data)
            raise UpdateFailed(f"No unit provided for {energy_type}")

        return {
            "tariffs": tariffs_today,
            "tariffs_tomorrow": tariffs_tomorrow,
            "unit": _normalize_unit(unit),
            "min_price": min(amounts),
            "avg_price": sum(amounts) / len(amounts),
            "max_price": max(amounts),
        }

    async def _async_update_data(self) -> EssentData:
        """Fetch data from API."""
        session = async_get_clientsession(self.hass)
        try:
            response = await session.get(
                API_ENDPOINT,
                timeout=CLIENT_TIMEOUT,
                headers={"Accept": "application/json"},
            )
        except ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        raw_body = await response.text()
        if response.status != HTTPStatus.OK:
            _LOGGER.debug(
                "Essent API %s returned %s with body: %s",
                API_ENDPOINT,
                response.status,
                raw_body,
            )
            raise UpdateFailed(f"Error fetching data: {response.status}")

        try:
            data = await response.json()
        except ValueError as err:
            _LOGGER.debug("Failed to decode JSON body: %s", raw_body)
            raise UpdateFailed(f"Invalid JSON received: {err}") from err

        prices = data.get("prices") or []
        if not prices:
            _LOGGER.debug("No price data available in response: %s", data)
            raise UpdateFailed("No price data available")

        current_date = dt_util.now().date().isoformat()
        today: dict[str, Any] | None = None
        tomorrow: dict[str, Any] | None = None

        for idx, price in enumerate(prices):
            if price.get("date") == current_date:
                today = price
                if idx + 1 < len(prices):
                    tomorrow = prices[idx + 1]
                break

        if today is None:
            today = prices[0]
            tomorrow = prices[1] if len(prices) > 1 else None
            _LOGGER.debug(
                "No price entry found for %s, falling back to first date %s",
                current_date,
                today.get("date"),
            )

        if not isinstance(today, dict):
            raise UpdateFailed("Invalid data structure for current prices")

        electricity_block = today.get("electricity")
        gas_block = today.get("gas")

        if not isinstance(electricity_block, dict) or not isinstance(gas_block, dict):
            _LOGGER.debug("Missing electricity or gas block in payload: %s", today)
            raise UpdateFailed("Response missing electricity or gas data")

        return {
            "electricity": self._normalize_energy_block(
                electricity_block,
                "electricity",
                tomorrow.get("electricity") if isinstance(tomorrow, dict) else None,
            ),
            "gas": self._normalize_energy_block(
                gas_block,
                "gas",
                tomorrow.get("gas") if isinstance(tomorrow, dict) else None,
            ),
        }
