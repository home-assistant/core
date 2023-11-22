"""La Marzocco Cloud API client."""
from collections.abc import Callable, Mapping
import logging
from typing import Any

from lmcloud import LMCloud
from lmcloud.exceptions import BluetoothConnectionFailed

from homeassistant.components import bluetooth
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_MACHINE

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoClient(LMCloud):
    """Keep data for La Marzocco entities."""

    _bt_disconnected = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: Mapping[str, Any],
        callback_websocket_notify: Callable[[], None] | None = None,
    ) -> None:
        """Initialise the LaMarzocco entity data."""
        super().__init__(callback_websocket_notify)
        self._entry_data = entry_data
        self.hass = hass

    async def connect(self) -> None:
        """Connect to the machine."""
        _LOGGER.debug("Initializing Cloud API")
        await self._init_cloud_api(
            credentials=self._entry_data,
            machine_serial=self._entry_data.get(CONF_MACHINE),
        )
        _LOGGER.debug("Model name: %s", self.model_name)

        username: str = self._entry_data.get(CONF_USERNAME, "")
        mac_address: str = self._entry_data.get(CONF_MAC, "")
        name: str = self._entry_data.get(CONF_NAME, "")

        if mac_address and name:
            # coming from discovery
            _LOGGER.debug("Initializing with known Bluetooth device")
            await self._init_bluetooth_with_known_device(username, mac_address, name)
        else:
            # check if there are any bluetooth adapters to use
            count = bluetooth.async_scanner_count(self.hass, connectable=True)
            if count > 0:
                _LOGGER.debug("Found Bluetooth adapters, initializing with Bluetooth")
                bt_scanner = bluetooth.async_get_scanner(self.hass)

                await self._init_bluetooth(
                    username=username,
                    init_client=False,
                    bluetooth_scanner=bt_scanner,
                )

        if self._lm_bluetooth:
            _LOGGER.debug("Connecting to machine with Bluetooth")
            await self.get_hass_bt_client()

        host: str = self._entry_data.get(CONF_HOST, "")
        if host:
            _LOGGER.debug("Initializing local API")
            await self._init_local_api(host)

    async def update_machine_status(self) -> None:
        """Update the machine status."""
        if not self._initialized:
            await self.connect()
            self._initialized = True

        elif self._initialized and not self._websocket_initialized:
            # only initialize websockets after the first update
            await self._init_websocket()

            await self.update_local_machine_status(force_update=True)

    async def set_power(self, enabled: bool) -> None:
        """Set the power state of the machine."""
        await self.get_hass_bt_client()
        await super().set_power(enabled)

    async def set_steam_boiler_enable(self, enable: bool) -> None:
        """Set the steam boiler state of the machine."""
        await self.get_hass_bt_client()
        await self.set_steam(enable)

    async def set_coffee_temp(self, temperature: float) -> None:
        """Set the coffee temperature of the machine."""
        await self.get_hass_bt_client()
        await super().set_coffee_temp(temperature)

    async def set_steam_temp(self, temperature: int) -> None:
        """Set the steam temperature of the machine."""
        possible_temps = [126, 128, 131]
        min(possible_temps, key=lambda x: abs(x - temperature))
        await self.get_hass_bt_client()
        await super().set_steam_temp(temperature)

    async def get_hass_bt_client(self) -> None:
        """Get a Bleak Client for the machine."""
        # according to HA best practices, we should not reuse the same client
        # get a new BLE device from hass and init a new Bleak Client with it
        if self._lm_bluetooth is None:
            return

        assert self._lm_bluetooth.address
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._lm_bluetooth.address, connectable=True
        )

        if ble_device is None:
            if not self._bt_disconnected:
                _LOGGER.warning(
                    "Machine not found in Bluetooth scan, not sending commands through bluetooth"
                )
                self._bt_disconnected = True
            return

        if self._bt_disconnected:
            _LOGGER.warning(
                "Machine available again for Bluetooth, sending commands through bluetooth"
            )
            self._bt_disconnected = False
        try:
            await self._lm_bluetooth.new_bleak_client_from_ble_device(ble_device)
        except BluetoothConnectionFailed as ex:
            _LOGGER.warning(ex)
