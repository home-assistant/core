"""Switch platform for Hatch Rest."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HatchRestEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hatch Rest control switch."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([HatchRestSwitch(coordinator)], True)


class HatchRestSwitch(HatchRestEntity, SwitchEntity):
    """Master control switch for Hatch Rest device."""

    @property
    def name(self) -> str:
        """Hatch Rest switch name."""
        return f"{super().device_name} power"

    @property
    def is_on(self) -> bool:
        """Power state of Hatch Rest device."""
        return self._device.power

    async def async_turn_on(self, **_):
        """Turn on the Hatch Rest device."""
        if not self.is_on:
            await self._device.power_on()
            self._device.power = True

        self.async_write_ha_state()

    async def async_turn_off(self, **_):
        """Turn off the Hatch Rest device."""
        if self.is_on:
            await self._device.power_off()
            self._device.power = False

        self.async_write_ha_state()
