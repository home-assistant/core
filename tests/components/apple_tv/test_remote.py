"""Test apple_tv remote."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.apple_tv.remote import AppleTVRemote
from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
)


@pytest.mark.parametrize(
    ("command", "method", "hold_secs"),
    [
        ("up", "remote_control.up", 0.0),
        ("wakeup", "power.turn_on", 0.0),
        ("volume_up", "audio.volume_up", 0.0),
        ("home", "remote_control.home", 1.0),
        ("select", "remote_control.select", 1.0),
    ],
    ids=["up", "wakeup", "volume_up", "home", "select"],
)
async def test_send_command(command: str, method: str, hold_secs: float) -> None:
    """Test "send_command" method."""
    remote = AppleTVRemote("test", "test", None)
    remote.atv = AsyncMock()
    await remote.async_send_command(
        [command],
        **{ATTR_NUM_REPEATS: 1, ATTR_DELAY_SECS: 0, ATTR_HOLD_SECS: hold_secs},
    )
    assert len(remote.atv.method_calls) == 1
    if hold_secs >= 1:
        assert (
            str(remote.atv.method_calls[0])
            == f"call.{method}(action=<InputAction.Hold: 2>)"
        )
    else:
        assert str(remote.atv.method_calls[0]) == f"call.{method}()"
