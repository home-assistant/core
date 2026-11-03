"""Switch platform for Atomberg."""

from typing import Any, override

from atomberg_api import (
    COMMAND_IDLE_SLEEP,
    COMMAND_SLEEP,
    COMMAND_SLEEP_WINDOW,
    DEVICE_TYPE_FAN,
    DEVICE_TYPE_WATER_PURIFIER,
    AtombergDevice,
)

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AtombergConfigEntry, AtombergCoordinator
from .entity import AtombergEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AtombergConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Atomberg switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = [
        AtombergSleepSwitch(coordinator, device)
        for device in coordinator.devices_of_type(DEVICE_TYPE_FAN)
        if COMMAND_SLEEP in device.supported_commands
    ]
    for device in coordinator.devices_of_type(DEVICE_TYPE_WATER_PURIFIER):
        if coordinator.supports_setting(device, COMMAND_IDLE_SLEEP):
            entities.append(AtombergIdleSleepSwitch(coordinator, device))
        if coordinator.supports_setting(device, COMMAND_SLEEP_WINDOW):
            entities.append(AtombergSleepWindowSwitch(coordinator, device))
    async_add_entities(entities)


class AtombergSleepSwitch(AtombergEntity, SwitchEntity):
    """Fan sleep mode switch."""

    _attr_translation_key = "sleep_mode"

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device, COMMAND_SLEEP)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether sleep mode is on."""
        return bool(self.device_state[COMMAND_SLEEP])

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn sleep mode on."""
        await self._async_send({COMMAND_SLEEP: True}, {COMMAND_SLEEP: True})

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn sleep mode off."""
        await self._async_send({COMMAND_SLEEP: False}, {COMMAND_SLEEP: False})


class AtombergIdleSleepSwitch(AtombergEntity, SwitchEntity):
    """Water purifier display sleep while idle."""

    _attr_translation_key = "idle_sleep"

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device, COMMAND_IDLE_SLEEP)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether idle display sleep is on."""
        return bool(self.device_state.get(COMMAND_IDLE_SLEEP))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn idle display sleep on."""
        await self._async_send({COMMAND_IDLE_SLEEP: 1}, {COMMAND_IDLE_SLEEP: 1})

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn idle display sleep off."""
        await self._async_send({COMMAND_IDLE_SLEEP: 0}, {COMMAND_IDLE_SLEEP: 0})


class AtombergSleepWindowSwitch(AtombergEntity, SwitchEntity):
    """Water purifier daily sleep window."""

    _attr_translation_key = "sleep_window"

    def __init__(
        self, coordinator: AtombergCoordinator, device: AtombergDevice
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device, COMMAND_SLEEP_WINDOW)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the sleep window is enabled."""
        return bool(self.device_state.get(COMMAND_SLEEP_WINDOW))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the sleep window."""
        await self.coordinator.async_set_sleep_window(self.device.device_id, True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the sleep window."""
        await self.coordinator.async_set_sleep_window(self.device.device_id, False)
