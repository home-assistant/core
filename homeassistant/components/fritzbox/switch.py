"""Support for AVM FRITZ!SmartHome switch devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxDeviceEntity
from .coordinator import FritzboxConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FritzboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the FRITZ!SmartHome switch from ConfigEntry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities(devices: set[str] | None = None) -> None:
        """Add devices."""
        if devices is None:
            devices = coordinator.new_devices
        if not devices:
            return
        async_add_entities(
            FritzboxSwitch(coordinator, ain)
            for ain in devices
            if coordinator.data.devices[ain].has_switch
        )

    entry.async_on_unload(coordinator.async_add_listener(_add_entities))

    _add_entities(set(coordinator.data.devices))


class FritzboxSwitch(FritzBoxDeviceEntity, SwitchEntity):
    """The switch class for FRITZ!SmartHome switches."""

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.data.switch_state  # type: ignore [no-any-return]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(self.data.set_switch_state_on)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self.data.set_switch_state_off)
        await self.coordinator.async_refresh()
