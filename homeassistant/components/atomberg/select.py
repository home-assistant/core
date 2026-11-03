"""Select platform for Atomberg."""

from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import (
    COMMAND_FALLBACK_MODE,
    COMMAND_MODE,
    COMMAND_TIMER,
    DEVICE_TYPE_FAN,
    DEVICE_TYPE_WATER_PURIFIER,
    AtombergDevice,
)
from .const import (
    TIMER_HOURS,
    TIMER_OPTIONS,
    WATER_PURIFIER_FALLBACK_MODES,
    WATER_PURIFIER_MODES,
)
from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg selects."""
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [
        AtombergTimerSelect(coordinator, device)
        for device in coordinator.devices_of_type(DEVICE_TYPE_FAN)
        if COMMAND_TIMER in device.supported_commands
    ]
    for device in coordinator.devices_of_type(DEVICE_TYPE_WATER_PURIFIER):
        if coordinator.supports_setting(device, COMMAND_MODE):
            entities.append(AtombergWaterPurifierModeSelect(coordinator, device))
        if coordinator.supports_setting(device, COMMAND_FALLBACK_MODE):
            entities.append(
                AtombergWaterPurifierFallbackModeSelect(coordinator, device)
            )
    async_add_entities(entities)


class AtombergTimerSelect(AtombergEntity, SelectEntity):
    """Fan off timer select."""

    _attr_translation_key = "timer"
    _attr_options = TIMER_OPTIONS

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, device, COMMAND_TIMER)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the active timer."""
        hours = self.device_state["timer_hours"]
        if hours not in TIMER_HOURS:
            return None
        return TIMER_OPTIONS[TIMER_HOURS.index(hours)]

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the timer."""
        index = TIMER_OPTIONS.index(option)
        await self._async_send(
            {COMMAND_TIMER: index}, {"timer_hours": TIMER_HOURS[index]}
        )


class AtombergWaterPurifierModeSelect(AtombergEntity, SelectEntity):
    """Water purifier purification mode select."""

    _attr_translation_key = "purification_mode"
    _command = COMMAND_MODE
    _modes = WATER_PURIFIER_MODES

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, device, self._command)
        self._attr_options = list(self._modes.values())

    @property
    @override
    def current_option(self) -> str | None:
        """Return the active mode."""
        mode = self.device_state.get(self._command)
        if mode is None:
            return None
        return self._modes.get(mode)

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the mode."""
        value = next(key for key, name in self._modes.items() if name == option)
        await self._async_send({self._command: value}, {self._command: value})


class AtombergWaterPurifierFallbackModeSelect(AtombergWaterPurifierModeSelect):
    """Water purifier fallback mode select."""

    _attr_translation_key = "fallback_mode"
    _command = COMMAND_FALLBACK_MODE
    _modes = WATER_PURIFIER_FALLBACK_MODES
