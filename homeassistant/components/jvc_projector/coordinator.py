"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from jvcprojector import JvcProjector, JvcProjectorTimeoutError, command as cmd

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NAME

if TYPE_CHECKING:
    from jvcprojector import Command


_LOGGER = logging.getLogger(__name__)

INTERVAL_SLOW = timedelta(seconds=10)
INTERVAL_FAST = timedelta(seconds=5)

CORE_COMMANDS: tuple[type[Command], ...] = (
    cmd.Power,
    cmd.Signal,
    cmd.Input,
    cmd.LightTime,
)

TRANSLATIONS = str.maketrans({"+": "p", "%": "p", ":": "x"})

TIMEOUT_RETRIES = 12
TIMEOUT_SLEEP = 1

type JVCConfigEntry = ConfigEntry[JvcProjectorDataUpdateCoordinator]


class JvcProjectorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Data update coordinator for the JVC Projector integration."""

    config_entry: JVCConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: JVCConfigEntry, device: JvcProjector
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=NAME,
            update_interval=INTERVAL_SLOW,
        )

        self.device: JvcProjector = device

        if TYPE_CHECKING:
            assert config_entry.unique_id is not None
        self.unique_id = config_entry.unique_id

        self.capabilities = self.device.capabilities()

        self.state: dict[type[Command], str] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Update state with the current value of a command."""
        commands: set[type[Command]] = set(self.async_contexts())
        commands = commands.difference(CORE_COMMANDS)

        last_timeout: JvcProjectorTimeoutError | None = None

        for _ in range(TIMEOUT_RETRIES):
            try:
                new_state = await self._get_device_state(commands)
                break
            except JvcProjectorTimeoutError as err:
                # Timeouts are expected when the projector loses signal and ignores commands for a brief time.
                last_timeout = err
                await asyncio.sleep(TIMEOUT_SLEEP)
        else:
            raise UpdateFailed(str(last_timeout)) from last_timeout

        # Clear state on signal loss
        if (
            new_state.get(cmd.Signal) == cmd.Signal.NONE
            and self.state.get(cmd.Signal) != cmd.Signal.NONE
        ):
            self.state = {k: v for k, v in self.state.items() if k in CORE_COMMANDS}

        # Update state with new values
        for k, v in new_state.items():
            self.state[k] = v

        if self.state[cmd.Power] != cmd.Power.STANDBY:
            self.update_interval = INTERVAL_FAST
        else:
            self.update_interval = INTERVAL_SLOW

        return {k.name: v for k, v in self.state.items()}

    async def _get_device_state(
        self, commands: set[type[Command]]
    ) -> dict[type[Command], str]:
        """Get the current state of the device."""
        new_state: dict[type[Command], str] = {}
        deferred_commands: list[type[Command]] = []

        power = await self._update_command_state(cmd.Power, new_state)

        if power == cmd.Power.ON:
            signal = await self._update_command_state(cmd.Signal, new_state)
            await self._update_command_state(cmd.Input, new_state)
            await self._update_command_state(cmd.LightTime, new_state)

            if signal == cmd.Signal.SIGNAL:
                for command in commands:
                    if command.depends:
                        # Command has dependencies so defer until below
                        deferred_commands.append(command)
                    else:
                        await self._update_command_state(command, new_state)

                # Deferred commands should have had dependencies met above
                for command in deferred_commands:
                    depend_command, depend_values = next(iter(command.depends.items()))
                    value: str | None = None
                    if depend_command in new_state:
                        value = new_state[depend_command]
                    elif depend_command in self.state:
                        value = self.state[depend_command]
                    if value and value in depend_values:
                        await self._update_command_state(command, new_state)

        elif self.state.get(cmd.Signal) != cmd.Signal.NONE:
            new_state[cmd.Signal] = cmd.Signal.NONE

        return new_state

    async def _update_command_state(
        self, command: type[Command], new_state: dict[type[Command], str]
    ) -> str | None:
        """Update state with the current value of a command."""
        value = await self.device.get(command)

        if value != self.state.get(command):
            new_state[command] = value

        return value

    def get_options_map(self, command: str) -> dict[str, str]:
        """Get the available options for a command."""
        capabilities = self.capabilities.get(command, {})

        if TYPE_CHECKING:
            assert isinstance(capabilities, dict)
            assert isinstance(capabilities.get("parameter", {}), dict)
            assert isinstance(capabilities.get("parameter", {}).get("read", {}), dict)

        values = list(capabilities.get("parameter", {}).get("read", {}).values())

        return {v: v.translate(TRANSLATIONS) for v in values}

    def supports(self, command: type[Command]) -> bool:
        """Check if the device supports a command."""
        return self.device.supports(command)
