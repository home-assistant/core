"""Switch representing the shutoff valve for the Flo by Moen integration."""

from typing import List

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

from .const import DOMAIN as FLO_DOMAIN
from .device import FloDeviceDataUpdateCoordinator
from .entity import FloEntity


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flo switches from config entry."""
    devices: List[FloDeviceDataUpdateCoordinator] = hass.data[FLO_DOMAIN]["devices"]
    async_add_entities([FloSwitch(device) for device in devices])


class FloSwitch(FloEntity, SwitchEntity):
    """Switch class for the Flo by Moen valve."""

    def __init__(self, device: FloDeviceDataUpdateCoordinator):
        """Initialize the Flo switch."""
        super().__init__("shutoff_valve", "Shutoff Valve", device)
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

    @callback
    def async_update_state(self) -> None:
        """Retrieve the latest valve state and update the state machine."""
        self._state = self._device.last_known_valve_state == "open"
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._device.async_add_listener(self.async_update_state))
