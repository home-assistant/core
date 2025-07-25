"""Data UpdateCoordinator for the Remote Calendar integration."""

from datetime import timedelta
import logging

from httpx import HTTPError, InvalidURL, TimeoutException
from ical.calendar import Calendar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import get_calendar
from .const import DOMAIN
from .ics import InvalidIcsException, parse_calendar

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
            name=f"{DOMAIN}_{config_entry.title}",
            update_interval=SCAN_INTERVAL,
            always_update=True,
        )
        self._client = get_async_client(hass)
        self._url = config_entry.data[CONF_URL]

    async def _async_update_data(self) -> Calendar:
        """Update data from the url."""
        try:
            res = await get_calendar(self._client, self._url)
            res.raise_for_status()
        except TimeoutException as err:
            _LOGGER.debug("%s: %s", self._url, str(err) or type(err).__name__)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout",
            ) from err
        except (HTTPError, InvalidURL) as err:
            _LOGGER.debug("%s: %s", self._url, str(err) or type(err).__name__)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            ) from err
        try:
            self.ics = res.text
            return await parse_calendar(self.hass, res.text)
        except InvalidIcsException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_parse",
                translation_placeholders={"err": str(err)},
            ) from err
