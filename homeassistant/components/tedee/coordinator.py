import logging
import time
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)
from pytedee_async import (TedeeAuthException, TedeeClientException,
                           TedeeDataUpdateException, TedeeLocalAuthException,
                           TedeeWebhookException)

SCAN_INTERVAL = timedelta(seconds=20)
STALE_DATA_INTERVAL = 300

_LOGGER = logging.getLogger(__name__)



class TedeeApiCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the tedee API centrally"""

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
        self._tedee_client = tedee_client
        self._initialized = False
        self._next_get_locks = time.time()
        self._last_data_update = time.time()
        self._stale_data = False


    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        if (time.time() - self._last_data_update) >= STALE_DATA_INTERVAL and not self._stale_data:
            _LOGGER.warn("Data hasn't been updated for more than %s minutes. \
                            Check your connection to the Tedee Bridge/the internet or reload the integration.", \
                            str(int(STALE_DATA_INTERVAL/60))
                        )
            self._stale_data = True
        elif (time.time() - self._last_data_update) < STALE_DATA_INTERVAL and self._stale_data:
            _LOGGER.warn("Tedee receiving updated data again.")
            self._stale_data = False

        try:
            _LOGGER.debug("Update coordinator: Getting locks from API")

            # once every hours get all lock details, otherwise use the sync endpoint
            if self._next_get_locks - time.time() <= 0:
                _LOGGER.debug("Updating through /my/lock endpoint...")
                await self._tedee_client.get_locks()
                self._next_get_locks = time.time() + 60*60
            else:
                _LOGGER.debug("Updating through /sync endpoint...")
                await self._tedee_client.sync()

            self._last_data_update = time.time()

        except TedeeLocalAuthException as ex:
            msg = "Authentication failed. \
                    Local access token is invalid"
            raise ConfigEntryAuthFailed(msg) from ex
                
            
        except TedeeAuthException as ex:
            # TODO: remove this
            _LOGGER.error(ex, exc_info=True)
            msg = "Authentication failed. \
                        Personal Key is either invalid, doesn't have the correct scopes \
                        (Devices: Read, Locks: Operate) or is expired."
            raise ConfigEntryAuthFailed(msg) from ex

        except TedeeDataUpdateException as ex:
            _LOGGER.debug("Error while updating data: %s", ex)
        except (TedeeClientException, Exception) as ex:
            _LOGGER.error(ex)
            raise UpdateFailed("Querying API failed. Error: %s", ex)
        
        if not self._tedee_client.locks_dict:
            # No locks found; abort setup routine.
            _LOGGER.warn("No locks found in your account.")

        _LOGGER.debug("available_locks: %s", ", ".join(map(str, self._tedee_client.locks_dict.keys())))

        if not self._initialized:
            self._initialized = True

        return self._tedee_client.locks_dict
    

    @callback
    def webhook_received(self, data: dict) -> None:
        _LOGGER.debug("Webhook received: %s", str(data))
        try:
            self._tedee_client.parse_webhook_message(data)
        except TedeeWebhookException as ex:
            _LOGGER.warn(ex)
            return
        
        self._last_data_update = time.time()

        if self._initialized:
            self.async_set_updated_data(self._tedee_client.locks_dict) # update listeners and reset coordinator timer
        else:
            self.async_update_listeners() # update listeners without resetting coordinator timer