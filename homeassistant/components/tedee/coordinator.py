"""Coordinator for Tedee locks."""
import asyncio
from datetime import timedelta
import logging
import time

from pytedee_async import (
    TedeeAuthException,
    TedeeClient,
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
    TedeeLock,
    TedeeWebhookException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BRIDGE_ID, CONF_LOCAL_ACCESS_TOKEN, DOMAIN

SCAN_INTERVAL = timedelta(seconds=20)
STALE_DATA_INTERVAL = 300

_LOGGER = logging.getLogger(__name__)


class TedeeApiCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the tedee API centrally."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        bridge_id_str = entry.data.get(CONF_BRIDGE_ID)
        bridge_id: int | None = None
        if bridge_id_str:
            bridge_id = int(bridge_id_str)
        self.tedee_client = TedeeClient(
            personal_token=entry.data.get(CONF_ACCESS_TOKEN),
            local_token=entry.data.get(CONF_LOCAL_ACCESS_TOKEN),
            local_ip=entry.data.get(CONF_HOST),
            bridge_id=bridge_id,
        )
        self._initialized = False
        self._next_get_locks = time.time()
        self._last_data_update = time.time()
        self._stale_data = False
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[int, TedeeLock]:
        """Fetch data from API endpoint."""
        if (
            time.time() - self._last_data_update
        ) >= STALE_DATA_INTERVAL and not self._stale_data:
            _LOGGER.warning(
                "Data hasn't been updated for more than %s minutes. \
                            Check your connection to the Tedee Bridge/the internet or reload the integration",
                str(int(STALE_DATA_INTERVAL / 60)),
            )
            self._stale_data = True
        elif (
            time.time() - self._last_data_update
        ) < STALE_DATA_INTERVAL and self._stale_data:
            _LOGGER.warning("Tedee receiving updated data again")
            self._stale_data = False

        try:
            _LOGGER.debug("Update coordinator: Getting locks from API")

            # once every hours get all lock details, otherwise use the sync endpoint
            if self._next_get_locks - time.time() <= 0:
                _LOGGER.debug("Updating through /my/lock endpoint")
                await self.tedee_client.get_locks()
                self._next_get_locks = time.time() + 60 * 60
            else:
                _LOGGER.debug("Updating through /sync endpoint")
                await self.tedee_client.sync()

            self._last_data_update = time.time()

        except TedeeLocalAuthException as ex:
            raise ConfigEntryAuthFailed(
                "Authentication failed. Local access token is invalid"
            ) from ex

        except TedeeAuthException as ex:
            raise ConfigEntryAuthFailed(
                "Authentication failed.  Personal Key is either invalid, doesn't have the correct scopes (Devices: Read, Locks: Operate) or is expired"
            ) from ex

        except TedeeDataUpdateException as ex:
            _LOGGER.debug("Error while updating data: %s", str(ex))
        except (TedeeClientException, asyncio.TimeoutError) as ex:
            raise UpdateFailed("Querying API failed. Error: %s" % str(ex)) from ex

        if not self.tedee_client.locks_dict:
            # No locks found; abort setup routine.
            _LOGGER.warning("No locks found in your account")

        _LOGGER.debug(
            "available_locks: %s",
            ", ".join(map(str, self.tedee_client.locks_dict.keys())),
        )

        if not self._initialized:
            self._initialized = True

        return self.tedee_client.locks_dict

    @callback
    def webhook_received(self, data: dict) -> None:
        """Handle webhook message."""
        _LOGGER.debug("Webhook received: %s", str(data))
        try:
            self.tedee_client.parse_webhook_message(data)
        except TedeeWebhookException as ex:
            _LOGGER.warning(ex)
            return

        self._last_data_update = time.time()

        if self._initialized:
            self.async_set_updated_data(
                self.tedee_client.locks_dict
            )  # update listeners and reset coordinator timer
        else:
            self.async_update_listeners()  # update listeners without resetting coordinator timer
