"""Tests for the Velbus entity base class."""

from unittest.mock import AsyncMock

import pytest
from velbusaio.channels import Channel as VelbusChannel

from homeassistant.components.velbus.entity import VelbusEntity


@pytest.mark.parametrize(
    ("module_serial", "expected_unique_id"),
    [
        ("a1b2c3d4e5f6", "a1b2c3d4e5f6-2"),
        (None, "5-2"),
        ("", "5-2"),
        # Modules like the VMB4RY report a serial of "0"; without a fallback two
        # such modules would share the same unique_id.
        ("0", "5-2"),
    ],
)
def test_unique_id_falls_back_to_module_address(
    module_serial: str | None, expected_unique_id: str
) -> None:
    """Test that a missing or "0" module serial falls back to the module address."""
    channel = AsyncMock(spec=VelbusChannel)
    channel.get_module_address.return_value = 5
    channel.get_channel_number.return_value = 2
    channel.get_module_serial.return_value = module_serial
    channel.get_name.return_value = "channel"

    entity = VelbusEntity(channel)

    assert entity.unique_id == expected_unique_id
