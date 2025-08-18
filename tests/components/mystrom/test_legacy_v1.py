"""Tests for legacy myStrom v1 fallback (missing 'type')."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import get_default_device_response
from tests.common import MockConfigEntry


async def test_v1_switch_fallback_setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test that setup falls back to LegacyMyStromV1Switch when lib get_state raises KeyError."""
    # get_device_info returns response without 'type' (typical for v1)
    v1_info = get_default_device_response(None)

    class DummyRaisingSwitch:
        async def get_state(self):  # noqa: D401
            # Simulate library raising KeyError due to missing 'type' in response
            raise KeyError("type")

    with (
        patch("pymystrom.get_device_info", side_effect=AsyncMock(return_value=v1_info)),
        patch(
            "homeassistant.components.mystrom._get_mystrom_switch",
            return_value=DummyRaisingSwitch(),
        ),
        # Avoid real network calls in legacy client; pretend it connects
        patch(
            "homeassistant.components.mystrom.legacy.LegacyMyStromV1Switch.get_state",
            side_effect=AsyncMock(return_value=None),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Entity should be created and entry loaded despite missing 'type'
    state = hass.states.get("switch.mystrom_device")
    assert state is not None
    assert config_entry.state is ConfigEntryState.LOADED

