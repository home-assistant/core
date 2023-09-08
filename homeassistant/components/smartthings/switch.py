"""Support for switches through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import Capability

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add switches for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    switches = []
    for device in broker.devices.values():
        for component in device.components:
            if component in device.status.disabled_components:
                continue
            if "switch" in device.components[component]:
                switches.append(SmartThingsSwitch(device, component))
    async_add_entities(switches)


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    # Must be able to be turned on/off.
    if Capability.switch in capabilities:
        return [Capability.switch, Capability.energy_meter, Capability.power_meter]
    return None


class SmartThingsSwitch(SmartThingsEntity, SwitchEntity):
    """Define a SmartThings switch."""

    def __init__(self, device, component):
        """Init the class."""
        super().__init__(device)
        self._component = component

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        if self._component == "main":
            return f"{self._device.label} switch"
        return f"{self._device.label} {self._component} switch"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        if self._component == "main":
            return f"{self._device.device_id}"
        return f"{self._device.device_id}.{self._component}"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._device.switch_off(set_status=True, component_id=self._component)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._device.switch_on(set_status=True, component_id=self._component)
        # State is set optimistically in the command above, therefore update
        # the entity state ahead of receiving the confirming push updates
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if self._component == "main":
            return self._device.status.switch
        return self._device.status.components[self._component].switch
