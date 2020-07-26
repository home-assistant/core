"""Switch representing the shutoff valve for the Flo by Moen integration."""

from typing import List

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDevice
from .entity import FloEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo switches from config entry."""
    devices: List[FloDevice] = hass.data[FLO_DOMAIN]["devices"]
    async_add_entities([FloSwitch(device) for device in devices])


class FloSwitch(FloEntity, SwitchEntity):
    """Switch class for the Flo by Moen valve."""

    def __init__(self, device: FloDevice):
        """Initialize the Flo switch."""
        super().__init__(f"{device.mac_address}_shutoff_valve", "Shutoff Valve", device)
        self._state = self._device.last_known_valve_state == "open"

    @property
    def is_on(self) -> bool:
        """Return True if the valve is open."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use for the valve."""
        if self.is_on:
            return "mdi:valve-open"
        else:
            return "mdi:valve-closed"

    async def async_turn_on(self, **kwargs) -> None:
        """Open the valve."""
        await self._device.api_client.device.open_valve(self._device.id)
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Close the valve."""
        await self._device.api_client.device.close_valve(self._device.id)
        self._state = False
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Retrieve the latest valve state and update the state machine."""
        self._state = self._device.last_known_valve_state == "open"
        self.async_write_ha_state()
