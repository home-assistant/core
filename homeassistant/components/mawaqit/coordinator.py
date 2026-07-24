"""Coordinators for the Mawaqit integration."""

from datetime import datetime, timedelta
import logging
from typing import override

from mawaqit.exceptions import BadCredentialsException, MawaqitException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from . import mawaqit_wrapper
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MosqueCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to fetch mosque information."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the mosque coordinator."""
        self.mosque_uuid: str = config_entry.data[CONF_UUID]
        self.token: str | None = config_entry.data.get(CONF_API_KEY)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Mosque Data",
            update_method=self._async_update_data,
            update_interval=timedelta(days=1),
        )

    @override
    async def _async_update_data(self) -> dict:
        """Fetch mosque details from the API."""
        try:
            mosque_data = await mawaqit_wrapper.fetch_mosque_by_id(
                self.mosque_uuid,
                token=self.token,
                session=async_get_clientsession(self.hass),
            )
        except BadCredentialsException as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except MawaqitException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="mawaqit_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except (ConnectionError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="network_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if not mosque_data:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_mosque_data",
            )

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

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="Prayer Times",
            update_method=self._async_update_data,
            update_interval=timedelta(minutes=1),
        )

    @override
    async def _async_update_data(self) -> dict:
        """Fetch prayer times from API and notify sensors.

        We fetch the prayer times twice per day, but the coordinator updates every
        minute so that sensors can re-evaluate which prayer is upcoming.
        """
        now = dt_util.utcnow()
        prayer_times: dict | None = None

        if (
            not self.last_fetch
            or ((now - self.last_fetch) > timedelta(hours=12))
            or (self.data is None)
        ):
            try:
                prayer_times = await mawaqit_wrapper.fetch_prayer_times(
                    mosque=self.mosque_uuid,
                    token=self.token,
                    session=async_get_clientsession(self.hass),
                )
                self.last_fetch = now
            except BadCredentialsException as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="auth_failed",
                ) from err
            except MawaqitException as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="mawaqit_error",
                    translation_placeholders={"error": str(err)},
                ) from err
            except (ConnectionError, TimeoutError) as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="network_error",
                    translation_placeholders={"error": str(err)},
                ) from err

            if not prayer_times:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_prayer_times_data",
                )

            # return fresh data when fetched
            return prayer_times

        # return existing data so sensors re-evaluate
        return self.data
