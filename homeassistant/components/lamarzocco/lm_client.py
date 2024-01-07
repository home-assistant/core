"""La Marzocco Cloud API client."""
from collections.abc import Callable
import logging

from bleak.backends.device import BLEDevice
from lmcloud import LMCloud

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

    async def set_power_hass(self, enabled: bool) -> bool:
        """Set the power state of the machine."""
        return await self.set_power(enabled, await self.get_hass_ble_device())

    async def set_steam_boiler_hass(self, enable: bool) -> bool:
        """Set the steam boiler state of the machine."""
        return await self.set_steam(enable, await self.get_hass_ble_device())

    async def set_coffee_temp_hass(self, temperature: float) -> bool:
        """Set the coffee temperature of the machine."""
        return await self.set_coffee_temp(temperature, await self.get_hass_ble_device())

    async def set_steam_temp_hass(self, temperature: int) -> bool:
        """Set the steam temperature of the machine."""
        return await self.set_steam_temp(temperature, await self.get_hass_ble_device())

    async def get_hass_ble_device(self) -> BLEDevice | None:
        """Get a Bleak Client for the machine."""
        # according to HA best practices, we should not reuse the same client
        # get a new BLE device from hass and init a new Bleak Client with it
        if self._lm_bluetooth is None:
            return None

        return bluetooth.async_ble_device_from_address(
            self.hass, self._lm_bluetooth.address, connectable=True
        )
