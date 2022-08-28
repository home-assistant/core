"""Support for Melnor RainCloud sprinkler water timer."""

from __future__ import annotations

from typing import Any, cast

from melnor_bluetooth.device import Valve

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_CONNECTION_TIMEOUT, DOMAIN
from .models import MelnorBluetoothBaseEntity, MelnorDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    switches = []

    coordinator: MelnorDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    await coordinator.data.connect(timeout=DEFAULT_CONNECTION_TIMEOUT)
    if not coordinator.data.is_connected:
        raise PlatformNotReady(f"Failed to connect to: {coordinator.data.mac}")

    # This device may not have 4 valves total, but the library will only expose the right number of valves
    for i in range(1, 5):
        if coordinator.data[f"zone{i}"] is not None:
            switches.append(MelnorSwitch(coordinator, i))

    async_add_devices(switches, True)


class MelnorSwitch(MelnorBluetoothBaseEntity, SwitchEntity):
    """A switch implementation for a melnor device."""

    _valve_index: int

    def __init__(
        self,
        coordinator: MelnorDataUpdateCoordinator,
        valve_index: int,
    ) -> None:
        """Initialize a switch for a melnor device."""
        super().__init__(coordinator)
        self._valve_index = valve_index

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._valve().is_watering

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._valve().is_watering = True
        await self._device.push_state()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._valve().is_watering = False
        await self._device.push_state()
        await self.coordinator.async_refresh()

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return "mdi:sprinkler"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return f"{self._device.name} Zone {self._valve().id+1}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the switch."""
        return f"{self._attr_unique_id}-zone{self._valve().id}"

    def _valve(self) -> Valve:
        return cast(Valve, self.coordinator.data[f"zone{self._valve_index}"])
