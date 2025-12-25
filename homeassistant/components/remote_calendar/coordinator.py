"""Data UpdateCoordinator for the Remote Calendar integration."""

from datetime import timedelta
import logging

from httpx import HTTPError, InvalidURL, TimeoutException
from ical.calendar import Calendar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
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
            config_entry=config_entry,
            always_update=True,
        )
        self._client = get_async_client(hass)
        self._url = config_entry.data[CONF_URL]
        self._username = config_entry.data.get(CONF_USERNAME)
        self._password = config_entry.data.get(CONF_PASSWORD)

    async def _async_update_data(self) -> Calendar:
        """Update data from the url."""
        _LOGGER.debug("Updating calendar data from: %s", self._url)
        try:
            res = await get_calendar(
                self._client,
                self._url,
                username=self._username,
                password=self._password,
            )
            _LOGGER.debug(
                "Calendar update response: status=%s, content_length=%s",
                res.status_code,
                len(res.text) if res.text else 0,
            )
            res.raise_for_status()
        except TimeoutException as err:
            _LOGGER.debug(
                "Timeout updating calendar from %s: %s",
                self._url,
                str(err) or type(err).__name__,
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout",
            ) from err
        except (HTTPError, InvalidURL) as err:
            _LOGGER.debug(
                "HTTP error updating calendar from %s: %s (type: %s)",
                self._url,
                str(err) or type(err).__name__,
                type(err).__name__,
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unable_to_fetch",
            ) from err
        else:
            try:
                self.ics = res.text
                _LOGGER.debug(
                    "Parsing calendar data, ICS length: %s bytes", len(self.ics)
                )
                parsed = await parse_calendar(self.hass, res.text)
            except InvalidIcsException as err:
                _LOGGER.debug("Failed to parse calendar ICS: %s", err)
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="unable_to_parse",
                    translation_placeholders={"err": str(err)},
                ) from err
            else:
                _LOGGER.debug("Calendar parsed successfully")
                return parsed
