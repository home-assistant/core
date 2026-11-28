"""Data update coordinator for the Osmund integration."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import logging
from typing import override

from osmund import (
    API_ACCESS_OPEN,
    RESOLUTION_HOUR,
    RESOLUTION_QUARTER_HOUR,
    SCOPE_PRICES,
    Location,
    OsmundAccessError,
    OsmundAuthError,
    OsmundClient,
    OsmundConnectionError,
    OsmundError,
    OsmundScopeError,
    OsmundUnavailableError,
    PriceDay,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# The calls are shared with the customer's other tools: the API counts the
# calls of all of a customer's keys together. An update reads the locations
# (one call) and, per location, only the price days it does not hold yet:
# about 50 to 60 calls a day for one location.
UPDATE_INTERVAL = timedelta(minutes=30)
# Tomorrow's prices are published in the afternoon.
TOMORROW_FROM = time(13, 0)
# The Danish calendar decides "today" and "tomorrow" for prices, whatever time
# zone Home Assistant runs in.
DANISH_TIME_ZONE = "Europe/Copenhagen"

type OsmundConfigEntry = ConfigEntry[OsmundCoordinator]


@dataclass(slots=True)
class OsmundData:
    """What the integration holds between updates."""

    locations: dict[str, Location] = field(default_factory=dict)
    # Per location the API answers for: the price days it holds, today and tomorrow only.
    prices: dict[str, dict[date, PriceDay]] = field(default_factory=dict)


def danish_now() -> datetime:
    """Now, in Danish time."""
    return dt_util.now(dt_util.get_time_zone(DANISH_TIME_ZONE))


def price_resolution(location: Location) -> str:
    """Prices by the quarter hour where the meter measures quarter hours, else by the hour.

    A meter that measures hours is billed at the average of the hour's four
    quarter-hour prices, which is what the hourly resolution answers.
    """
    if location.meter_resolution == RESOLUTION_QUARTER_HOUR:
        return RESOLUTION_QUARTER_HOUR
    return RESOLUTION_HOUR


class OsmundCoordinator(DataUpdateCoordinator[OsmundData]):
    """Every location the key can read, and its prices for today and tomorrow."""

    config_entry: OsmundConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OsmundConfigEntry,
        client: OsmundClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    @override
    async def _async_setup(self) -> None:
        """Check once that the key works and can read prices."""
        try:
            key = await self.client.me()
        except OsmundError as err:
            raise _update_error(err) from err
        if SCOPE_PRICES not in key.scopes:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="missing_scope"
            )

    @override
    async def _async_update_data(self) -> OsmundData:
        """Read the locations, then only the price days that are missing or not complete."""
        now = danish_now()
        # Before the first update there is no data yet.
        held = self.data.prices if self.data is not None else {}
        try:
            locations = await self.client.locations()
        except OsmundError as err:
            raise _update_error(err) from err
        if not any(location.api_access == API_ACCESS_OPEN for location in locations):
            # Nothing to show: at setup, Home Assistant tries again later; after
            # it, the sensors are unavailable until a location has access again.
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_access")
        prices: dict[str, dict[date, PriceDay]] = {}
        for location in locations:
            if location.api_access != API_ACCESS_OPEN:
                continue
            try:
                prices[location.id] = await self._price_days(
                    location, held.get(location.id, {}), now
                )
            except OsmundAccessError:
                # The location lost its access between two calls: no prices for it.
                continue
            except OsmundError as err:
                raise _update_error(err) from err
        return OsmundData(
            locations={location.id: location for location in locations},
            prices=prices,
        )

    async def _price_days(
        self, location: Location, held: dict[date, PriceDay], now: datetime
    ) -> dict[date, PriceDay]:
        """Today's and tomorrow's prices at one location, fetching only what is missing.

        Tomorrow is read from the afternoon, so at midnight today's prices are
        already held.
        """
        today = now.date()
        tomorrow = today + timedelta(days=1)
        resolution = price_resolution(location)
        # Yesterday's tomorrow is today: it is kept, not fetched again.
        days = {day: held[day] for day in (today, tomorrow) if day in held}
        if _needs(days.get(today), resolution):
            days[today] = await self.client.prices(location.id, today, resolution)
        if now.time() >= TOMORROW_FROM and _needs(days.get(tomorrow), resolution):
            # Until tomorrow is published, the API answers with complete false.
            days[tomorrow] = await self.client.prices(location.id, tomorrow, resolution)
        return days


def _needs(day: PriceDay | None, resolution: str) -> bool:
    """Whether a price day must be fetched (again)."""
    return (
        day is None
        or not day.complete
        or not day.intervals
        or day.resolution != resolution
    )


def _update_error(err: OsmundError) -> Exception:
    """The Home Assistant error an API error stands for."""
    if isinstance(err, OsmundAuthError):
        return ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        )
    if isinstance(err, OsmundScopeError):
        return ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="missing_scope"
        )
    if isinstance(err, OsmundUnavailableError):
        # The calls are shared with the customer's other tools: wait as long as the API says.
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="unavailable",
            retry_after=err.retry_after,
        )
    if isinstance(err, OsmundConnectionError):
        return UpdateFailedUnreachable(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        )
    return UpdateFailed(translation_domain=DOMAIN, translation_key="api_error")
