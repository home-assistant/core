"""Class for helpers and community with the OverKiz API."""
import logging
from typing import Any, Optional

from pyhoma.models import Command, Device

from .coordinator import TahomaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class OverkizExecutor:
    """Representation of an Overkiz device with execution handler."""

    def __init__(self, device_url: str, coordinator: TahomaDataUpdateCoordinator):
        """Initialize the executor."""
        self.device_url = device_url
        self.coordinator = coordinator

    @property
    def device(self) -> Device:
        """Return TaHoma device linked to this entity."""
        return self.coordinator.data[self.device_url]

    def select_command(self, *commands: str) -> Optional[str]:
        """Select first existing command in a list of commands."""
        existing_commands = self.device.definition.commands
        return next((c for c in commands if c in existing_commands), None)

    def has_command(self, *commands: str) -> bool:
        """Return True if a command exists in a list of commands."""
        return self.select_command(*commands) is not None

    def select_state(self, *states) -> Optional[str]:
        """Select first existing active state in a list of states."""
        if self.device.states:
            return next(
                (
                    state.value
                    for state in self.device.states
                    if state.name in list(states)
                ),
                None,
            )
        return None

    def has_state(self, *states: str) -> bool:
        """Return True if a state exists in self."""
        return self.select_state(*states) is not None

    async def async_execute_command(self, command_name: str, *args: Any):
        """Execute device command in async context."""
        try:
            exec_id = await self.coordinator.client.execute_command(
                self.device.deviceurl,
                Command(command_name, list(args)),
                "Home Assistant",
            )
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error(exception)
            return

        # ExecutionRegisteredEvent doesn't contain the deviceurl, thus we need to register it here
        self.coordinator.executions[exec_id] = {
            "deviceurl": self.device.deviceurl,
            "command_name": command_name,
        }

        await self.coordinator.async_refresh()

    async def async_cancel_command(self, exec_id: str):
        """Cancel device command in async context."""
        await self.coordinator.client.cancel_command(exec_id)
