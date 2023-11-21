"""Coordinator for La Marzocco API."""
from datetime import timedelta
import logging
from typing import Any

from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .lm_client import LaMarzoccoClient

SCAN_INTERVAL = timedelta(seconds=30)
UPDATE_DELAY = 2

_LOGGER = logging.getLogger(__name__)


class LmApiCoordinator(DataUpdateCoordinator[LaMarzoccoClient]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    @property
    def lm(self) -> LaMarzoccoClient:
        """Return the La Marzocco API object."""
        return self._lm

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self._lm = LaMarzoccoClient(hass, entry.data)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> LaMarzoccoClient:
        """Fetch data from API endpoint."""
        try:
            _LOGGER.debug("Update coordinator: Updating data")
            await self._lm.update_machine_status(callback=self._on_data_received)

        except AuthFail as ex:
            msg = "Authentication failed. \
                            Maybe one of your credential details was invalid or you changed your password."
            _LOGGER.debug(msg, exc_info=True)
            raise ConfigEntryAuthFailed(msg) from ex
        except RequestNotSuccessful as ex:
            _LOGGER.debug(ex, exc_info=True)
            raise UpdateFailed("Querying API failed. Error: %s" % ex) from ex

        _LOGGER.debug("Current status: %s", str(self._lm.current_status))
        return self._lm

    @callback
    def _on_data_received(self, property_updated: str, value: Any) -> None:
        """Handle data received from websocket."""

        if not property_updated or not self._lm.initialized:
            return

        _LOGGER.debug(
            "Received data from websocket, property updated: %s with value: %s",
            str(property_updated),
            str(value),
        )
        self._lm.update_current_status(property_updated, value)

        self.data = self._lm

        self.async_update_listeners()
