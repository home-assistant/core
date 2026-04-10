"""Coordinators for the Mawaqit integration."""

from datetime import datetime, timedelta
import logging

from mawaqit.consts import BadCredentialsException, NoMosqueAround, NoMosqueFound

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from . import mawaqit_wrapper
from .const import CONF_UUID

_LOGGER = logging.getLogger(__name__)


class MosqueCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch mosque information."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the mosque coordinator."""
        self.mosque_uuid = config_entry.data.get(CONF_UUID)
        self.token = config_entry.data.get(CONF_API_KEY)

        super().__init__(
            hass,
            _LOGGER,
            name="Mosque Data",
            update_method=self._async_update_data,
            update_interval=timedelta(days=1),
        )

    async def _async_update_data(self) -> dict:
        """Fetch mosque details from the API."""
        try:
            mosque_data = await mawaqit_wrapper.fetch_mosque_by_id(
                self.mosque_uuid, token=self.token
            )
        except BadCredentialsException as err:
            raise ConfigEntryAuthFailed(f"Bad credentials: {err}") from err
        except (NoMosqueAround, NoMosqueFound) as err:
            raise UpdateFailed(f"No mosque found: {err}") from err
        except (ConnectionError, TimeoutError) as err:
            raise UpdateFailed(f"Network error: {err}") from err

        if not mosque_data:
            raise UpdateFailed("No mosque data found from the API")

        return mosque_data


class PrayerTimeCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch prayer times from the Mawaqit API.

    The API is called once per day to fetch the full prayer calendar.
    The coordinator updates every minute so that sensors tracking the
    next prayer can re-evaluate which prayer is upcoming.
    """

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the prayer time coordinator."""
        self.mosque_uuid = config_entry.data.get(CONF_UUID)
        self.token = config_entry.data.get(CONF_API_KEY)
        self.last_fetch: datetime | None = None
        self.prayer_times: dict | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Prayer Times",
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=1),
        )

    async def _async_update_data(self) -> dict:
        """Fetch prayer times from API and notify sensors."""
        now = dt_util.utcnow()

        if (
            not self.last_fetch
            or ((now - self.last_fetch) > timedelta(days=1))
            or (self.prayer_times is None)
        ):
            try:
                self.prayer_times = await mawaqit_wrapper.fetch_prayer_times(
                    mosque=self.mosque_uuid, token=self.token
                )
                self.last_fetch = now
            except BadCredentialsException as err:
                raise ConfigEntryAuthFailed(f"Bad credentials: {err}") from err
            except (NoMosqueAround, NoMosqueFound) as err:
                raise UpdateFailed(f"No mosque found: {err}") from err
            except (ConnectionError, TimeoutError) as err:
                raise UpdateFailed(f"Network error: {err}") from err

        if not self.prayer_times:
            raise UpdateFailed("No data received from API")

        return self.prayer_times
