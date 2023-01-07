"""Platform for EVSE Numbers."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity
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
    new_devices.append(CurrentNumber(evse))

    async_add_entities(new_devices)


class CurrentNumber(NumberEntity):
    """Number to set the current on evse."""

    def __init__(self, evse):
        """Initialize the CurrentNumber."""
        self.evse = evse
        self._attr_unique_id = f"{self.evse.name}_charge_current"
        self._attr_name = f"{self.evse.name} Charge Current"
        self._attr_native_min_value = 6
        self._attr_native_max_value = evse.max_current
        self._attr_native_step = 1
        self._attr_device_class = NumberDeviceClass.CURRENT

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        return await self.evse.set_current(round(value))

    async def async_update(self) -> None:
        """Update the current value."""
        self._attr_native_value = self.evse.get_actual_current()
