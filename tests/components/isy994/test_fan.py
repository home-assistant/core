"""Test the ISY994 fan platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.isy994.fan import ISYFanProgramEntity


@pytest.mark.parametrize(
    ("method", "expected_call", "unexpected_call"),
    [
        pytest.param("async_turn_on", "run_then", "run_else", id="turn_on"),
        pytest.param("async_turn_off", "run_else", "run_then", id="turn_off"),
    ],
)
async def test_fan_program_actions(
    method: str,
    expected_call: str,
    unexpected_call: str,
) -> None:
    """Test ISYFanProgramEntity turn on/off calls correct program run method."""
    status = MagicMock()
    status.name = "Test Fan Program"
    status.isy.uuid = "test-uuid"
    status.address = "test-address"

    actions = MagicMock()
    actions.run_then = AsyncMock(return_value=True)
    actions.run_else = AsyncMock(return_value=True)

    entity = ISYFanProgramEntity("Test Fan Program", status, actions)
    await getattr(entity, method)()

    getattr(actions, expected_call).assert_called_once()
    getattr(actions, unexpected_call).assert_not_called()
