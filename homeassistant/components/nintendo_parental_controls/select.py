"""Nintendo Switch Parental Controls select entity definitions."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pynintendoparental.enum import DeviceTimerMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NintendoParentalControlsConfigEntry, NintendoUpdateCoordinator
from .entity import Device, NintendoDevice

PARALLEL_UPDATES = 1


class NintendoParentalSelect(StrEnum):
    """Store keys for Nintendo Parental Controls select entities."""

    TIMER_MODE = "timer_mode"


@dataclass(kw_only=True, frozen=True)
class NintendoParentalControlsSelectEntityDescription(SelectEntityDescription):
    """Description for Nintendo Parental Controls select entities."""

    get_option: Callable[[Device], DeviceTimerMode | None]
    set_option_fn: Callable[[Device, DeviceTimerMode], Coroutine[Any, Any, None]]
    options_enum: type[DeviceTimerMode]


SELECT_DESCRIPTIONS: tuple[NintendoParentalControlsSelectEntityDescription, ...] = (
    NintendoParentalControlsSelectEntityDescription(
        key=NintendoParentalSelect.TIMER_MODE,
        translation_key=NintendoParentalSelect.TIMER_MODE,
        get_option=lambda device: device.timer_mode,
        set_option_fn=lambda device, option: device.set_timer_mode(option),
        options_enum=DeviceTimerMode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NintendoParentalControlsConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform."""
    async_add_devices(
        NintendoParentalSelectEntity(
            coordinator=entry.runtime_data,
            device=device,
            description=description,
        )
        for device in entry.runtime_data.api.devices.values()
        for description in SELECT_DESCRIPTIONS
    )


class NintendoParentalSelectEntity(NintendoDevice, SelectEntity):
    """Nintendo Parental Controls select entity."""

    entity_description: NintendoParentalControlsSelectEntityDescription

    def __init__(
        self,
        coordinator: NintendoUpdateCoordinator,
        device: Device,
        description: NintendoParentalControlsSelectEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator=coordinator, device=device, key=description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        option = self.entity_description.get_option(self._device)
        return option.name.lower() if option else None

    @property
    def options(self) -> list[str]:
        """Return a list of available options."""
        return [option.name.lower() for option in self.entity_description.options_enum]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        enum_option = self.entity_description.options_enum[option.upper()]
        await self.entity_description.set_option_fn(self._device, enum_option)
        await self.coordinator.async_request_refresh()
