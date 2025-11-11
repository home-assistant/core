"""Switch platform for Nintendo Parental."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pynintendoparental.enum import RestrictionMode

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NintendoParentalControlsConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

PARALLEL_UPDATES = 0


class NintendoParentalSwitch(StrEnum):
    """Store keys for Nintendo Parental Controls switches."""

    SUSPEND_SOFTWARE = "suspend_software"


@dataclass(kw_only=True, frozen=True)
class NintendoParentalControlsSwitchEntityDescription(SwitchEntityDescription):
    """Description for Nintendo Parental Controls switch entities."""

    is_on: Callable[[Device], bool | None]
    turn_on_fn: Callable[[Device], Coroutine[Any, Any, None]]
    turn_off_fn: Callable[[Device], Coroutine[Any, Any, None]]


SWITCH_DESCRIPTIONS: tuple[NintendoParentalControlsSwitchEntityDescription, ...] = (
    NintendoParentalControlsSwitchEntityDescription(
        key=NintendoParentalSwitch.SUSPEND_SOFTWARE,
        translation_key=NintendoParentalSwitch.SUSPEND_SOFTWARE,
        device_class=SwitchDeviceClass.SWITCH,
        is_on=lambda device: device.forced_termination_mode,
        turn_off_fn=lambda device: device.set_restriction_mode(RestrictionMode.ALARM),
        turn_on_fn=lambda device: device.set_restriction_mode(
            RestrictionMode.FORCED_TERMINATION
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalControlsConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    async_add_devices(
        NintendoParentalControlsSwitchEntity(entry.runtime_data, device, switch)
        for device in entry.runtime_data.api.devices.values()
        for switch in SWITCH_DESCRIPTIONS
    )


class NintendoParentalControlsSwitchEntity(NintendoDevice, SwitchEntity):
    """Represent a single switch."""

    entity_description: NintendoParentalControlsSwitchEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        description: NintendoParentalControlsSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return entity state."""
        return self.entity_description.is_on(self._device)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on_fn(self._device)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off_fn(self._device)
