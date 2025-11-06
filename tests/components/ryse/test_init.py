"""Tests for RYSE init setup."""

import pytest

from homeassistant.components.ryse import async_setup_entry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for the RYSE integration."""
    return MockConfigEntry(
        domain="ryse",
        data={"address": "AA:BB:CC:DD:EE:FF"},
        title="Mock RYSE Device",
    )


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up integration."""
    mock_config_entry.add_to_hass(hass)

    called = {}

    async def fake_forward_entry_setups(entry, platforms):
        called["entry"] = entry
        called["platforms"] = platforms

    # Use monkeypatch fixture provided by pytest instead of context manager
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            hass.config_entries,
            "async_forward_entry_setups",
            fake_forward_entry_setups,
        )

        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert called["platforms"] == [Platform.COVER]
    assert called["entry"] == mock_config_entry
