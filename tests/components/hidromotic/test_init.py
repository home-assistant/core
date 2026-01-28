"""Tests for the Hidromotic integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.hidromotic.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when device cannot be reached."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.hidromotic.HidromoticClient",
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.connect = AsyncMock(return_value=False)
        client.disconnect = AsyncMock()
        client.register_callback = MagicMock(return_value=lambda: None)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test successful unload of config entry."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_and_unload_multiple_entries(
    hass: HomeAssistant,
    mock_client: MagicMock,
) -> None:
    """Test setup and unload of multiple config entries."""
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.100",
        data={"host": "192.168.1.100"},
        title="Device 1",
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.101",
        data={"host": "192.168.1.101"},
        title="Device 2",
    )

    # Add and setup first entry
    entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()
    assert entry1.state is ConfigEntryState.LOADED

    # Add and setup second entry
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()
    assert entry2.state is ConfigEntryState.LOADED

    # Unload first entry
    await hass.config_entries.async_unload(entry1.entry_id)
    await hass.async_block_till_done()

    assert entry1.state is ConfigEntryState.NOT_LOADED
    assert entry2.state is ConfigEntryState.LOADED
