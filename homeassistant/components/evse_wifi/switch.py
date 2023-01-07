"""Platform for EVSE Switches."""
from __future__ import annotations

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    evse = hass.data[DOMAIN][config_entry.entry_id]

    new_devices = []
    new_devices.append(ChargeStateSwitch(evse))
    async_add_entities(new_devices)


class ChargeStateSwitch(SwitchEntity):
    """Set the charge state of the EVSE."""

    def __init__(self, evse):
        """Initiallize the Switch."""
        self.evse = evse
        self._attr_unique_id = f"{self.evse.name}_charge_state"
        self._attr_name = f"{self.evse.name} Charge State"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    async def async_turn_on(self, **kwargs):
        """Turn on the EVSE Charging."""
        return await self.evse.set_status(status=True)

    async def async_turn_off(self, **kwargs):
        """Turn off the EVSE Charging."""
        return await self.evse.set_status(status=False)

    async def async_toggle(self, **kwargs):
        """Toggle the EVSE Charging."""
        return await self.evse.set_status(status=not self.is_on)

    async def async_update(self):
        """Update the current value."""
        self._attr_is_on = self.evse.get_evse_state()
