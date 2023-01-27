"""Common tools used for the Tradfri test suite."""
from copy import deepcopy
from typing import Any
from unittest.mock import Mock

from pytradfri.device import Device

from homeassistant.components import tradfri
from homeassistant.core import HomeAssistant

from . import GATEWAY_ID

from tests.common import MockConfigEntry


async def setup_integration(hass):
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


async def trigger_observe_callback(
    hass: HomeAssistant,
    mock_gateway: Mock,
    device: Device,
    new_device_state: dict[str, Any] | None = None,
) -> None:
    """Trigger the observe callback."""
    observe_command = next(
        (
            command
            for command in mock_gateway.mock_commands
            if command.path == device.path and command.observe
        ),
        None,
    )
    assert observe_command

    if new_device_state is not None:
        mock_gateway.mock_responses.append(new_device_state)

    device_state = deepcopy(device.raw)
    new_state = mock_gateway.mock_responses[-1]
    device_state = modify_state(device_state, new_state)
    observe_command.process_result(device_state)

    await hass.async_block_till_done()
