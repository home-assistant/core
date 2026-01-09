"""Data update coordinator for the jvc_projector integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from jvcprojector import (
    JvcProjector,
    JvcProjectorAuthError,
    JvcProjectorTimeoutError,
    command as cmd,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import NAME

if TYPE_CHECKING:
    from jvcprojector import Command


_LOGGER = logging.getLogger(__name__)

INTERVAL_SLOW = timedelta(seconds=10)
INTERVAL_FAST = timedelta(seconds=5)

CORE_COMMANDS: tuple[type[Command], ...] = (cmd.Power, cmd.Signal, cmd.Input)

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

        self.capabilities: dict[str, Any] = {}
        self.state: dict[type[Command], str] = {}
        self.registered_commands: set[type[Command]] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        """Get the latest state data."""
        new_state: dict[type[Command], str] = {}
        deferred_commands: list[type[Command]] = []

        try:
            power = await self._update(cmd.Power, new_state)
            if power == cmd.Power.ON:
                await self._update(cmd.Input, new_state)

                signal = await self._update(cmd.Signal, new_state)
                if signal == cmd.Signal.SIGNAL:
                    # Update state for all enabled platform entities
                    for command in self.registered_commands:
                        if command.depends:
                            deferred_commands.append(command)
                        else:
                            await self._update(command, new_state)

                    # Update state for deferred dependencies
                    for command in deferred_commands:
                        depend_command, depend_values = next(
                            iter(command.depends.items())
                        )
                        value: str | None = None
                        if depend_command in new_state:
                            value = new_state[depend_command]
                        elif depend_command in self.state:
                            value = self.state[depend_command]
                        if value and value in depend_values:
                            await self._update(command, new_state)
                            break

            elif self.state.get(cmd.Signal) != cmd.Signal.NONE:
                new_state[cmd.Signal] = cmd.Signal.NONE

        except JvcProjectorTimeoutError as err:
            # Timeouts are expected when the projector loses signal and ignores commands for a brief time.
            self.last_update_success = False
            raise UpdateFailed(retry_after=1.0) from err

        if (
            new_state.get(cmd.Signal) == cmd.Signal.NONE
            and self.state.get(cmd.Signal) != cmd.Signal.NONE
        ):
            # Clear state on signal loss
            self.state = {k: v for k, v in self.state.items() if k in CORE_COMMANDS}

        for k, v in new_state.items():
            self.state[k] = v

        if self.state[cmd.Power] != cmd.Power.STANDBY:
            self.update_interval = INTERVAL_FAST
        else:
            self.update_interval = INTERVAL_SLOW

        return {k.name: v for k, v in self.state.items()}

    async def _update(
        self, command: type[Command], new_state: dict[type[Command], str]
    ) -> str | None:
        """Helper function to get command value."""
        value = await self.device.get(command)

        # Detect value changes
        if value != self.state.get(command):
            new_state[command] = value

        return value

    def get_options(self, command: str) -> list[str]:
        """Get the values for a command."""
        capability = self.capabilities.get(command)
        if not isinstance(capability, dict):
            return []

        parameter = capability.get("parameter")
        if not isinstance(parameter, dict):
            return []

        read = parameter.get("read")
        if not isinstance(read, dict):
            return []

        return list(read.values())

    def supports(self, command: type[Command]) -> bool:
        """Check if the device supports a command."""
        return self.device.supports(command)

    def register(self, command: type[Command]) -> None:
        """Register a command to get scheduled updates."""
        if command not in CORE_COMMANDS:
            self.registered_commands.add(command)

    def unregister(self, command: type[Command]) -> None:
        """Unregister a command to get scheduled updates."""
        if command in self.registered_commands:
            self.registered_commands.remove(command)
