"""Data UpdateCoordinator for the Remote Calendar integration."""

from datetime import timedelta
import logging

from httpx import HTTPError, InvalidURL
from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

type RemoteCalendarConfigEntry = ConfigEntry[RemoteCalendarDataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(days=1)


class RemoteCalendarDataUpdateCoordinator(DataUpdateCoordinator[Calendar]):
    """Class to manage fetching calendar data."""

    config_entry: RemoteCalendarConfigEntry
    ics: str

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
        self._client = get_async_client(hass)
        self._url = config_entry.data[CONF_URL]

    async def _async_update_data(self) -> Calendar:
        """Update data from the url."""
        try:
            res = await self._client.get(self._url, follow_redirects=True)
            res.raise_for_status()
        except (HTTPError, InvalidURL) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
                translation_placeholders={"err": str(err)},
            ) from err
        try:
            # calendar_from_ics will dynamically load packages
            # the first time it is called, so we need to do it
            # in a separate thread to avoid blocking the event loop
            self.ics = res.text
            return await self.hass.async_add_executor_job(
                IcsCalendarStream.calendar_from_ics, self.ics
            )
        except CalendarParseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_parse",
                translation_placeholders={"err": str(err)},
            ) from err
