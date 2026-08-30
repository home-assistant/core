"""Support for Sofar switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from sofar_modbus.modern.device import SofarInverter
from sofar_modbus.modern.enums import RemoteSwitchOnOff

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SofarSwitchEntityDescription(SwitchEntityDescription, SofarEntityDescription):
    """Describe a Sofar switch entity."""

    write_fn: Callable[[SofarInverter, bool], Awaitable[None]]


SWITCH_DESCRIPTIONS: tuple[SofarSwitchEntityDescription, ...] = (
    SofarSwitchEntityDescription(
        key="remote_switch_on_off",
        component="remote",
        name=None,
        write_fn=lambda device, value: device.remote.write(
            "remote_switch_on_off",
            RemoteSwitchOnOff.ON if value else RemoteSwitchOnOff.OFF,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar Inverter Modbus switch platform."""
    runtime_data = entry.runtime_data
    served = runtime_data.served_components
    async_add_entities(
        SofarSwitch(runtime_data, description)
        for description in SWITCH_DESCRIPTIONS
        if description.component in served
    )


class SofarSwitch(SofarEntity, SwitchEntity):
    """Defines a Sofar switch entity."""

    entity_description: SofarSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the remote switch is on."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        value = getattr(component, self.entity_description.key)
        return None if value is None else bool(value)

    async def _async_write(self, value: bool) -> None:
        """Write the switch state to the device."""
        await self.entity_description.write_fn(self.coordinator.device, value)
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the remote switch on."""
        await self._async_write(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the remote switch off."""
        await self._async_write(False)
