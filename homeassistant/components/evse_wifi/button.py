"""Platform for EVSE Buttons."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    new_devices.append(DoRebootButton(evse))
    async_add_entities(new_devices)


class DoRebootButton(ButtonEntity):
    """Button to reboot the EVSE."""

    def __init__(self, evse):
        """Initialize the Button."""
        self.evse = evse
        self._attr_unique_id = f"{self.evse.name}_do_reboot"
        self._attr_name = f"{self.evse.name} Reboot"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self.evse.devcie_info

    async def async_press(self) -> None:
        """Perform a rebbot of the EVSE."""
        return await self.evse.do_reboot()
