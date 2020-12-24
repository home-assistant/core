"""Support for Aqualink pool feature switches."""
from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import AqualinkEntity, refresh_system
from .const import DOMAIN as AQUALINK_DOMAIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[AQUALINK_DOMAIN][DOMAIN]:
        devs.append(HassAqualinkSwitch(dev))
    async_add_entities(devs, True)


class HassAqualinkSwitch(AqualinkEntity, SwitchEntity):
    """Representation of a switch."""

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self.dev.label

    @property
    def icon(self) -> str:
        """Return an icon based on the switch type."""
        if self.name == "Cleaner":
            return "mdi:robot-vacuum"
        if self.name == "Waterfall" or self.name.endswith("Dscnt"):
            return "mdi:fountain"
        if self.name.endswith("Pump") or self.name.endswith("Blower"):
            return "mdi:fan"
        if self.name.endswith("Heater"):
            return "mdi:radiator"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on or not."""
        return self.dev.is_on

    @refresh_system
    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        await self.dev.turn_on()

    @refresh_system
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        await self.dev.turn_off()
