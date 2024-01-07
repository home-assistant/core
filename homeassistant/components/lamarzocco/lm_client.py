"""La Marzocco Cloud API client."""
from collections.abc import Callable
import logging

from lmcloud import LMCloud
from lmcloud.exceptions import BluetoothConnectionFailed

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class LaMarzoccoClient(LMCloud):
    """Keep data for La Marzocco entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        callback_websocket_notify: Callable[[], None] | None = None,
    ) -> None:
        """Initialise the LaMarzocco entity data."""
        super().__init__(callback_websocket_notify=callback_websocket_notify)
        self.hass = hass
        self._bt_disconnected = False

    async def set_power(self, enabled: bool) -> bool:
        """Set the power state of the machine."""
        await self.get_hass_bt_client()
        return await super().set_power(enabled)

    async def set_steam_boiler_enable(self, enable: bool) -> bool:
        """Set the steam boiler state of the machine."""
        await self.get_hass_bt_client()
        return await self.set_steam(enable)

    async def set_coffee_temp(self, temperature: float) -> bool:
        """Set the coffee temperature of the machine."""
        await self.get_hass_bt_client()
        return await super().set_coffee_temp(temperature)

    async def set_steam_temp(self, temperature: int) -> bool:
        """Set the steam temperature of the machine."""
        possible_temps = [126, 128, 131]
        min(possible_temps, key=lambda x: abs(x - temperature))
        await self.get_hass_bt_client()
        return await super().set_steam_temp(temperature)

    async def get_hass_bt_client(self) -> None:
        """Get a Bleak Client for the machine."""
        # according to HA best practices, we should not reuse the same client
        # get a new BLE device from hass and init a new Bleak Client with it
        if self._lm_bluetooth is None:
            return

        # should not be called before the client is initialized
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
