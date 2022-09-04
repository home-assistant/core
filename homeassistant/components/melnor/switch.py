"""Support for Melnor RainCloud sprinkler water timer."""

from __future__ import annotations

from typing import Any, cast

from melnor_bluetooth.device import Valve

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import MelnorBluetoothBaseEntity, MelnorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    switches = []

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # This device may not have 4 valves total, but the library will only expose the right number of valves
    for i in range(1, 5):
        if coordinator.data[f"zone{i}"] is not None:
            switches.append(MelnorSwitch(coordinator, i))

    async_add_devices(switches, True)


class MelnorSwitch(MelnorBluetoothBaseEntity, SwitchEntity):
    """A switch implementation for a melnor device."""

    _valve_index: int
    _attr_icon = "mdi:sprinkler"

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        valve_index: int,
    ) -> None:
        """Initialize a switch for a melnor device."""
        super().__init__(coordinator)
        self._valve_index = valve_index

        self._attr_unique_id = f"{self._attr_unique_id}-zone{self._valve().id}-manual"
        self._attr_name = f"{self._device.name} Zone {self._valve().id+1}"

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._valve().is_watering

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._valve().is_watering = True
        await self._device.push_state()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._valve().is_watering = False
        await self._device.push_state()
        self.async_write_ha_state()

    def _valve(self) -> Valve:
        return cast(Valve, self._device[f"zone{self._valve_index}"])
