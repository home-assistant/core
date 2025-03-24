"""Common tools used for the Tradfri test suite."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pytradfri.command import Command
from pytradfri.const import ATTR_ID
from pytradfri.device import Device
from pytradfri.gateway import Gateway

from homeassistant.components import tradfri
from homeassistant.core import HomeAssistant

from . import GATEWAY_ID

from tests.common import MockConfigEntry


@dataclass
class CommandStore:
    """Store commands and command responses for the API."""

    sent_commands: list[Command]
    mock_responses: dict[str, Any]

    def register_device(
        self, gateway: Gateway, device_response: dict[str, Any]
    ) -> None:
        """Register device response."""
        get_devices_command = gateway.get_devices()
        self.register_response(get_devices_command, [device_response[ATTR_ID]])
        get_device_command = gateway.get_device(device_response[ATTR_ID])
        self.register_response(get_device_command, device_response)

    def register_response(self, command: Command, response: Any) -> None:
        """Register command response."""
        self.mock_responses[command.path_str] = response

    def process_command(self, command: Command) -> Any | None:
        """Process command."""
        response = self.mock_responses.get(command.path_str)
        if response is None or command.process_result is None:
            return None
        return command.process_result(response)

    async def trigger_observe_callback(
        self,
        hass: HomeAssistant,
        device: Device,
        new_device_state: dict[str, Any] | None = None,
    ) -> None:
        """Trigger the observe callback."""
        observe_command = next(
            (
                command
                for command in self.sent_commands
                if command.path == device.path and command.observe
            ),
            None,
        )
        assert observe_command

        device_path = "/".join(str(v) for v in device.path)
        device_state = deepcopy(device.raw)

        # Create a default observed state based on the sent commands.
        for command in self.sent_commands:
            if (data := command.data) is None or command.path_str != device_path:
                continue
            device_state = modify_state(device_state, data)

        # Allow the test to override the default observed state.
        if new_device_state is not None:
            device_state = modify_state(device_state, new_device_state)

        observe_command.process_result(device_state)

        await hass.async_block_till_done()


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Load the Tradfri integration with a mock gateway."""
    entry = MockConfigEntry(
        domain=tradfri.DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "gateway_id": GATEWAY_ID,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def modify_state(
    state: dict[str, Any], partial_state: dict[str, Any]
) -> dict[str, Any]:
    """Modify a state with a partial state."""
    for key, value in partial_state.items():
        if isinstance(value, list):
            for index, item in enumerate(value):
                state[key][index] = modify_state(state[key][index], item)
        elif isinstance(value, dict):
            state[key] = modify_state(state[key], value)
        else:
            state[key] = value

    return state
