"""Test the Motionblinds integration setup."""

from types import SimpleNamespace

import pytest

from homeassistant.components.motion_blinds import async_remove_config_entry_device
from homeassistant.components.motion_blinds.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("mac", "expected_result"),
    [
        ("gateway", False),
        ("connected_blind", False),
        ("old_blind", True),
    ],
    ids=("Gateway", "Connected blind", "Disconnected blind"),
)
async def test_remove_config_entry_device(
    hass: HomeAssistant, mac: str, expected_result: bool
) -> None:
    """Test that only disconnected blinds can be removed."""
    gateway = SimpleNamespace(mac="gateway", device_list={"connected_blind": None})
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.runtime_data = SimpleNamespace(gateway=gateway)
    device_entry = SimpleNamespace(identifiers={(DOMAIN, mac)})

    assert (
        await async_remove_config_entry_device(hass, config_entry, device_entry)
        is expected_result
    )
