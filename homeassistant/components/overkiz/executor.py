"""Class for helpers and communication with the OverKiz API."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

from pyoverkiz.enums import OverkizCommand, Protocol
from pyoverkiz.exceptions import OverkizException
from pyoverkiz.models import Command, Device, StateDefinition
from pyoverkiz.types import StateType as OverkizStateType

from homeassistant.exceptions import HomeAssistantError

from .coordinator import OverkizDataUpdateCoordinator

# Commands that don't support setting
# the delay to another value
COMMANDS_WITHOUT_DELAY = [
    OverkizCommand.IDENTIFY,
    OverkizCommand.OFF,
    OverkizCommand.ON,
    OverkizCommand.ON_WITH_TIMER,
    OverkizCommand.TEST,
]


class OverkizExecutor:
    """Representation of an Overkiz device with execution handler."""

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Initialize the executor."""
        self.device_url = device_url
        self.coordinator = coordinator
        self.base_device_url = self.device_url.split("#")[0]

    @property
    def device(self) -> Device:
        """Return Overkiz device linked to this entity."""
        return self.coordinator.data[self.device_url]

    def linked_device(self, index: int) -> Device | None:
        """Return Overkiz device sharing the same base url."""
        return self.coordinator.data.get(f"{self.base_device_url}#{index}")

    def select_command(self, *commands: str) -> str | None:
        """Select first existing command in a list of commands."""
        existing_commands = self.device.definition.commands
        return next((c for c in commands if c in existing_commands), None)

    def has_command(self, *commands: str) -> bool:
        """Return True if a command exists in a list of commands."""
        return self.select_command(*commands) is not None

    def select_definition_state(self, *states: str) -> StateDefinition | None:
        """Select first existing definition state in a list of states."""
        for existing_state in self.device.definition.states:
            if existing_state.qualified_name in states:
                return existing_state
        return None

    def select_state(self, *states: str) -> OverkizStateType:
        """Select first existing active state in a list of states."""
        for state in states:
            if current_state := self.device.states[state]:
                return current_state.value

        return None

    def has_state(self, *states: str) -> bool:
        """Return True if a state exists in self."""
        return self.select_state(*states) is not None

    def select_attribute(self, *attributes: str) -> OverkizStateType:
        """Select first existing active state in a list of states."""
        for attribute in attributes:
            if current_attribute := self.device.attributes[attribute]:
                return current_attribute.value

        return None

    async def async_execute_command(self, command_name: str, *args: Any) -> None:
        """Execute device command in async context."""
        parameters = [arg for arg in args if arg is not None]
        # Set the execution duration to 0 seconds for RTS devices on supported commands
        # Default execution duration is 30 seconds and will block consecutive commands
        if (
            self.device.protocol == Protocol.RTS
            and command_name not in COMMANDS_WITHOUT_DELAY
        ):
            parameters.append(0)

        try:
            exec_id = await self.coordinator.client.execute_command(
                self.device.device_url,
                Command(command_name, parameters),
                "Home Assistant",
            )
        # Catch Overkiz exceptions to support `continue_on_error` functionality
        except OverkizException as exception:
            raise HomeAssistantError(exception) from exception

        # ExecutionRegisteredEvent doesn't contain the device_url, thus we need to register it here
        self.coordinator.executions[exec_id] = {
            "device_url": self.device.device_url,
            "command_name": command_name,
        }

        await self.coordinator.async_refresh()

    async def async_cancel_command(
        self, commands_to_cancel: list[OverkizCommand]
    ) -> bool:
        """Cancel running execution by command."""

        # Cancel a running execution
        # Retrieve executions initiated via Home Assistant from Data Update Coordinator queue
        exec_id = next(
            (
                exec_id
                # Reverse dictionary to cancel the last added execution
                for exec_id, execution in reversed(self.coordinator.executions.items())
                if execution.get("device_url") == self.device.device_url
                and execution.get("command_name") in commands_to_cancel
            ),
            None,
        )

        if exec_id:
            await self.async_cancel_execution(exec_id)
            return True

        # Retrieve executions initiated outside Home Assistant via API
        executions = cast(Any, await self.coordinator.client.get_current_executions())
        # executions.action_group is typed incorrectly in the upstream library
        # or the below code is incorrect.
        exec_id = next(
            (
                execution.id
                for execution in executions
                # Reverse dictionary to cancel the last added execution
                for action in reversed(execution.action_group.get("actions"))
                for command in action.get("commands")
                if action.get("device_url") == self.device.device_url
                and command.get("name") in commands_to_cancel
            ),
            None,
        )

        if exec_id:
            await self.async_cancel_execution(exec_id)
            return True

        return False

    async def async_cancel_execution(self, exec_id: str) -> None:
        """Cancel running execution via execution id."""
        await self.coordinator.client.cancel_command(exec_id)

    def get_gateway_id(self) -> str:
        """Retrieve gateway id from device url.

        device URL (<protocol>://<gatewayId>/<deviceAddress>[#<subsystemId>])
        """
        url = urlparse(self.device_url)
        return url.netloc
