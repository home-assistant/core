"""Test apple_tv remote."""
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.apple_tv.remote import AppleTVRemote
from homeassistant.components.remote import ATTR_DELAY_SECS, ATTR_NUM_REPEATS


@pytest.mark.parametrize(
    ("command", "method"),
    [
        ("up", "remote_control.up"),
        ("wakeup", "power.turn_on"),
        ("volume_up", "audio.volume_up"),
        ("home_hold", "remote_control.home"),
    ],
    ids=["up", "wakeup", "volume_up", "home_hold"],
)
async def test_send_command(command: str, method: str) -> None:
    """Test "send_command" method."""
    remote = AppleTVRemote("test", "test", None)
    remote.atv = AsyncMock()
    await remote.async_send_command(
        [command], **{ATTR_NUM_REPEATS: 1, ATTR_DELAY_SECS: 0}
    )
    assert len(remote.atv.method_calls) == 1
    assert str(remote.atv.method_calls[0]) == f"call.{method}()"
