"""Data coordinator for receiving Allpowers updates."""

import logging

from allpowers_ble import AllpowersBLE, models

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AllpowersBLECoordinator(DataUpdateCoordinator):
    """Data coordinator for receiving Allpowers updates."""

    def __init__(self, hass: HomeAssistant, allpowers_ble: AllpowersBLE) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self._allpowers_ble = allpowers_ble
        allpowers_ble.register_callback(self._async_handle_update)
        allpowers_ble.register_disconnected_callback(self._async_handle_disconnect)
        self.connected = False

    @callback
    def _async_handle_update(self, state: models.AllpowersState) -> None:
        """Just trigger the callbacks."""
        self.connected = True
        self.async_set_updated_data(True)

    @callback
    def _async_handle_disconnect(self) -> None:
        """Trigger the callbacks for disconnected."""
        self.connected = False
        self.async_update_listeners()
