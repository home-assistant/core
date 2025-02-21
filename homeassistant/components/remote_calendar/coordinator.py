"""Data UpdateCoordinator for the Remote Calendar integration."""

from datetime import timedelta
import logging

from httpx import ConnectError, HTTPStatusError, UnsupportedProtocol
from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(days=1)

type RemoteCalendarConfigEntry = ConfigEntry[RemoteCalendarDataUpdateCoordinator]


class RemoteCalendarDataUpdateCoordinator(DataUpdateCoordinator[Calendar]):
    """Class to manage fetching calendar data."""

    config_entry: RemoteCalendarConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RemoteCalendarConfigEntry,
    ) -> None:
        """Initialize data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            always_update=True,
        )
        self._etag = None
        self._client = get_async_client(hass)
        self._url = config_entry.data["url"]

    async def _async_update_data(self) -> Calendar:
        """Update data from the url."""
        headers: dict = {}
        try:
            res = await self._client.get(self._url, headers=headers)
            res.raise_for_status()
        except (UnsupportedProtocol, ConnectError, HTTPStatusError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
                translation_placeholders={"err": str(err)},
            ) from err
        else:
            try:
                await self.hass.async_add_executor_job(
                    IcsCalendarStream.calendar_from_ics, res.text
                )
            except CalendarParseError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_parse",
                    translation_placeholders={"err": str(err)},
                ) from err
            else:
                return await self.hass.async_add_executor_job(
                    IcsCalendarStream.calendar_from_ics, res.text
                )
