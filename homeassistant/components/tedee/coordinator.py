"""Coordinator for Tedee locks."""
from datetime import timedelta
import logging
import time

from pytedee_async import (
    TedeeAuthException,
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
    TedeeWebhookException,
)

from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

SCAN_INTERVAL = timedelta(seconds=20)
STALE_DATA_INTERVAL = 300

_LOGGER = logging.getLogger(__name__)


class TedeeApiCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the tedee API centrally."""

    def __init__(self, hass, tedee_client):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="tedee API coordinator",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=SCAN_INTERVAL,
        )
        self.tedee_client = tedee_client
        self._initialized = False
        self._next_get_locks = time.time()
        self._last_data_update = time.time()
        self._stale_data = False

    async def _async_update_data(self):
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
            msg = "Authentication failed. \
                    Local access token is invalid"
            raise ConfigEntryAuthFailed(msg) from ex

        except TedeeAuthException as ex:
            # TODO: remove this exception # pylint: disable=fixme
            _LOGGER.exception(ex)
            msg = "Authentication failed. \
                        Personal Key is either invalid, doesn't have the correct scopes \
                        (Devices: Read, Locks: Operate) or is expired"
            raise ConfigEntryAuthFailed(msg) from ex

        except TedeeDataUpdateException as ex:
            _LOGGER.debug("Error while updating data: %s", str(ex))
        except (TedeeClientException, Exception) as ex:
            _LOGGER.exception(ex)
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
