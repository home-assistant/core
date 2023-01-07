"""Data coordinator for receiving LD2410B updates."""

import logging

from ld2410_ble import LD2410BLE, LD2410BLEState

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LD2410BLECoordinator(DataUpdateCoordinator[None]):
    """Data coordinator for receiving LD2410B updates."""

    def __init__(self, hass: HomeAssistant, ld2410_ble: LD2410BLE) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self._ld2410_ble = ld2410_ble
        ld2410_ble.register_callback(self._async_handle_update)
        ld2410_ble.register_disconnected_callback(self._async_handle_disconnect)
        self.connected = False

    @callback
    def _async_handle_update(self, state: LD2410BLEState) -> None:
        """Just trigger the callbacks."""
        self.connected = True
        self.async_set_updated_data(None)

    @callback
    def _async_handle_disconnect(self) -> None:
        """Trigger the callbacks for disconnected."""
        self.connected = False
        self.async_update_listeners()
