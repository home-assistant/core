"""Class for helpers and communication with the OverKiz API."""

from typing import Any

from aiohttp import ClientConnectorError, ServerDisconnectedError
from pyoverkiz.enums import OverkizCommand
from pyoverkiz.exceptions import BaseOverkizError
from pyoverkiz.models import Action, Command, Device, StateDefinition

from homeassistant.exceptions import HomeAssistantError

from .coordinator import OverkizDataUpdateCoordinator


class OverkizExecutor:
    """Representation of an Overkiz device with execution handler."""

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Initialize the executor."""
        self.device_url = device_url
        self.coordinator = coordinator

    @property
    def device(self) -> Device:
        """Return Overkiz device linked to this entity."""
        return self.coordinator.data[self.device_url]

    def linked_device(self, index: int) -> Device | None:
        """Return Overkiz device sharing the same base url."""
        return self.coordinator.data.get(
            f"{self.device.identifier.base_device_url}#{index}"
        )

    def select_definition_state(self, *states: str) -> StateDefinition | None:
        """Select first existing definition state in a list of states."""
        for state_name in states:
            if state_name in self.device.definition.states:
                return self.device.definition.states[state_name]
        return None

    async def async_execute_command(
        self, command_name: str, *args: Any, refresh_afterwards: bool = True
    ) -> None:
        """Execute device command in async context.

        :param refresh_afterwards: Whether to refresh the device
            state after the command is executed. If several
            commands are executed, it will be refreshed only once.
        """
        parameters = [arg for arg in args if arg is not None]

        try:
            exec_id = await self.coordinator.client.execute_action_group(
                label="Home Assistant",
                actions=[
                    Action(
                        device_url=self.device.device_url,
                        commands=[Command(name=command_name, parameters=parameters)],
                    )
                ],
            )
        # Catch Overkiz exceptions to support `continue_on_error` functionality
        except BaseOverkizError as exception:
            raise HomeAssistantError(exception) from exception
        except (
            TimeoutError,
            ClientConnectorError,
            ServerDisconnectedError,
        ) as exception:
            raise HomeAssistantError("Failed to connect") from exception

        # ExecutionRegisteredEvent doesn't contain the device_url, thus we need
        # to register it here. The action queue can merge concurrent action
        # groups under one exec_id, so accumulate rather than overwrite.
        self.coordinator.executions.setdefault(exec_id, []).append(
            {
                "device_url": self.device.device_url,
                "command_name": command_name,
            }
        )
        if refresh_afterwards:
            await self.coordinator.async_refresh()

    async def async_execute_commands(
        self, commands: list[Command], refresh_afterwards: bool = True
    ) -> None:
        """Execute multiple device commands as a single batch execution.

        The Overkiz API processes all commands in order within a single action group,
        which is required when commands depend on each other.

        :param refresh_afterwards: Whether to refresh the device state
            after the batch is executed. Disable it to refresh only once
            when this batch is part of a larger sequence of commands.
        """
        if not commands:
            return

        try:
            exec_id = await self.coordinator.client.execute_action_group(
                label="Home Assistant",
                actions=[Action(device_url=self.device.device_url, commands=commands)],
            )
        # Catch Overkiz exceptions to support `continue_on_error` functionality
        except BaseOverkizError as exception:
            raise HomeAssistantError(exception) from exception
        except (
            TimeoutError,
            ClientConnectorError,
            ServerDisconnectedError,
        ) as exception:
            raise HomeAssistantError("Failed to connect") from exception

        self.coordinator.executions.setdefault(exec_id, []).append(
            {
                "device_url": self.device.device_url,
                "command_name": commands[-1].name,
            }
        )
        if refresh_afterwards:
            await self.coordinator.async_refresh()

    async def async_cancel_command(
        self, commands_to_cancel: list[OverkizCommand]
    ) -> bool:
        """Cancel running execution by command."""

        # Cancel a running execution. Retrieve executions
        # initiated via Home Assistant from Data Update
        # Coordinator queue
        exec_id = next(
            (
                exec_id
                # Reverse dictionary to cancel the last added execution
                for exec_id, executions in reversed(self.coordinator.executions.items())
                for execution in executions
                if execution.get("device_url") == self.device.device_url
                and execution.get("command_name") in commands_to_cancel
            ),
            None,
        )

        if exec_id:
            await self.async_cancel_execution(exec_id)
            return True

        # Retrieve executions initiated outside Home Assistant via API
        executions = await self.coordinator.client.get_current_executions()
        exec_id = next(
            (
                execution.id
                for execution in executions
                if execution.action_group
                for action in reversed(execution.action_group.actions)
                for command in action.commands
                if action.device_url == self.device.device_url
                and command.name in commands_to_cancel
            ),
            None,
        )

        if exec_id:
            await self.async_cancel_execution(exec_id)
            return True

        return False

    async def async_cancel_execution(self, exec_id: str) -> None:
        """Cancel running execution via execution id."""
        await self.coordinator.client.cancel_execution(exec_id)
