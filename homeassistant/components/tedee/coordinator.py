"""Coordinator for Tedee locks."""
from datetime import datetime, timedelta
import logging

from pytedee_async import (
    TedeeClient,
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
    TedeeLock,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LOCAL_ACCESS_TOKEN, DOMAIN

SCAN_INTERVAL = timedelta(seconds=20)

_LOGGER = logging.getLogger(__name__)


class TedeeApiCoordinator(DataUpdateCoordinator[dict[int, TedeeLock]]):
    """Class to handle fetching data from the tedee API centrally."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.tedee_client = TedeeClient(
            local_token=self.config_entry.data[CONF_LOCAL_ACCESS_TOKEN],
            local_ip=self.config_entry.data[CONF_HOST],
        )

        self._next_get_locks = datetime.now()

    async def _async_update_data(self) -> dict[int, TedeeLock]:
        """Fetch data from API endpoint."""

        _LOGGER.debug("Update coordinator: Getting locks from API")

        try:
            # once every hours get all lock details, otherwise use the sync endpoint
            if self._next_get_locks <= datetime.now():
                _LOGGER.debug("Updating through /my/lock endpoint")
                await self.tedee_client.get_locks()
                self._next_get_locks = datetime.now() + timedelta(hours=1)
            else:
                _LOGGER.debug("Updating through /sync endpoint")
                await self.tedee_client.sync()

        except TedeeLocalAuthException as ex:
            raise ConfigEntryError(
                "Authentication failed. Local access token is invalid"
            ) from ex

        except TedeeDataUpdateException as ex:
            _LOGGER.debug("Error while updating data: %s", str(ex))
            raise UpdateFailed("Error while updating data: %s" % str(ex)) from ex
        except (TedeeClientException, TimeoutError) as ex:
            raise UpdateFailed("Querying API failed. Error: %s" % str(ex)) from ex

        if not self.tedee_client.locks_dict:
            # No locks found; abort setup routine.
            _LOGGER.warning("No locks found in your account")
            raise UpdateFailed("No locks found in your account")

        _LOGGER.debug(
            "available_locks: %s",
            ", ".join(map(str, self.tedee_client.locks_dict.keys())),
        )

        return self.tedee_client.locks_dict
