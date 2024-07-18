"""Provides the LvivPowerOffCoordinator class for polling power off periods."""

import datetime
import logging

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POWEROFF_GROUP_CONF, UPDATE_INTERVAL, PowerOffGroup
from .energyua_scrapper import EnergyUaScrapper
from .entities import PowerOffPeriod

LOGGER = logging.getLogger(__name__)


class LvivPowerOffCoordinator(DataUpdateCoordinator):
    """Coordinates the polling of power off periods."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=datetime.timedelta(seconds=UPDATE_INTERVAL),
        )
        self.hass = hass
        self.config_entry = config_entry
        self.group: PowerOffGroup = config_entry.data[POWEROFF_GROUP_CONF]
        self.api = EnergyUaScrapper(self.group)
        self.periods: list[PowerOffPeriod] = []

    async def _async_update_data(self) -> dict:
        """Fetch power off periods from scrapper."""
        try:
            await self._fetch_periods()
            return {}  # noqa: TRY300
        except Exception as err:
            LOGGER.exception(
                "Cannot obtain power offs periods for group %s", self.group
            )
            msg = f"Power offs not polled: {err}"
            raise UpdateFailed(msg) from err

    async def _fetch_periods(self) -> None:
        self.periods = await self.api.get_power_off_periods()

    def get_event_at(self, at: datetime.datetime) -> CalendarEvent:
        """Get the current event."""
        for period in self.periods:
            start, end = period.to_datetime_period(at.tzinfo)
            if start <= at <= end:
                return self._get_calendar_event(start, end)

    def get_events_between(
        self,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Get all events."""
        events = []
        for period in self.periods:
            start, end = period.to_datetime_period(start_date.tzinfo)
            if start_date <= start <= end_date and start_date <= end <= end_date:
                events.append(self._get_calendar_event(start, end))
        return events

    def _get_calendar_event(
        self, start: datetime.datetime, end: datetime.datetime
    ) -> CalendarEvent:
        return CalendarEvent(
            start=start,
            end=end,
            summary="Power Off",
        )
