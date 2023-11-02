"""Coordinator for Acaia integration."""
from datetime import timedelta
import logging
from typing import Any

from bleak import BleakGATTCharacteristic
from pyacaia_async.decode import Message, Settings, decode

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .acaiaclient import AcaiaClient
from .const import BATTERY_LEVEL, GRAMS, UNITS, WEIGHT

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


class AcaiaApiCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the La Marzocco API centrally."""

    def __init__(self, hass: HomeAssistant, acaia_client: AcaiaClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Acaia API coordinator",
            update_interval=SCAN_INTERVAL,
        )
        self._device_available: bool = False
        self._data: dict[str, Any] = {BATTERY_LEVEL: None, UNITS: GRAMS, WEIGHT: 0.0}

        self._acaia_client: AcaiaClient = acaia_client

    @property
    def acaia_client(self) -> AcaiaClient:
        """Return the acaia client."""
        return self._acaia_client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data."""
        try:
            scanner_count = bluetooth.async_scanner_count(self.hass, connectable=True)
            if scanner_count == 0:
                self.acaia_client.connected = False
                _LOGGER.debug("Update coordinator: No bluetooth scanner available")
                return self._data

            self._device_available = bluetooth.async_address_present(
                self.hass, self._acaia_client.mac, connectable=True
            )

            if not self.acaia_client.connected and self._device_available:
                _LOGGER.debug("Update coordinator: Connecting")
                await self._acaia_client.connect(callback=self._on_data_received)

            elif not self._device_available:
                self.acaia_client.connected = False
                self.acaia_client.timer_running = False
                _LOGGER.debug(
                    "Update coordinator: Device with MAC %s not available",
                    self._acaia_client.mac,
                )

            else:
                # send auth to get the battery level and units
                await self._acaia_client.auth()
                await self._acaia_client.send_weight_notification_request()
        except Exception as ex:
            raise UpdateFailed("Error: %s" % ex) from ex

        return self._data

    @callback
    def _on_data_received(
        self, characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Receive data from scale."""
        msg = decode(data)[0]

        if isinstance(msg, Settings):
            self._data[BATTERY_LEVEL] = msg.battery
            self._data[UNITS] = msg.units
            _LOGGER.debug(
                "Got battery level %s, units %s", str(msg.battery), str(msg.units)
            )

        elif isinstance(msg, Message):
            self._data[WEIGHT] = msg.value
            _LOGGER.debug("Got weight %s", str(msg.value))

        self.async_update_listeners()
