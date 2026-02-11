"""Tests for the WLED integration."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wled import WLEDConnectionError

from homeassistant.components.wled.const import DOMAIN
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wled: AsyncMock
) -> None:
    """Test the WLED configuration entry unloading."""
    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable):
        connection_connected.set_result(None)
        await connection_finished

    # Mock out wled.listen with a Future
    mock_wled.listen.side_effect = connect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await connection_connected

    # Ensure config entry is loaded and are connected
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_wled.connect.call_count == 1
    assert mock_wled.disconnect.call_count == 0

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure everything is cleaned up nicely and are disconnected
    assert mock_wled.disconnect.call_count == 1


@patch(
    "homeassistant.components.wled.coordinator.WLED.request",
    side_effect=WLEDConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the WLED configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.fixture
def config_entry_v1() -> MockConfigEntry:
    """Return a WLED config entry at version 1.0 with a specific MAC."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.123"},
        unique_id="AABBCCDDEEFF",
        minor_version=1,
    )


@pytest.mark.usefixtures("mock_setup_entry", "mock_wled")
async def test_migrate_entry_future_version_is_downgrade(
    hass: HomeAssistant,
) -> None:
    """Return False when user downgraded from a future version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WLED Future",
        unique_id="AABBCCDDEEFF",
        version=2,
        minor_version=0,
        data={CONF_HOST: "wled.local"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert entry.state == ConfigEntryState.MIGRATION_ERROR
    assert entry.version == 2
    assert entry.minor_version == 0
    assert entry.unique_id == "AABBCCDDEEFF"


@pytest.mark.usefixtures("mock_setup_entry", "mock_wled")
async def test_migrate_entry_v1_to_1_2_no_duplicates(
    hass: HomeAssistant, config_entry_v1: MockConfigEntry
) -> None:
    """Migrate from 1.x to 1.2 when there are no other entries with same MAC."""
    config_entry_v1.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry_v1.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert config_entry_v1.state == ConfigEntryState.LOADED
    assert config_entry_v1.version == 1
    assert config_entry_v1.minor_version == 2
    assert config_entry_v1.unique_id == "aabbccddeeff"


@pytest.mark.usefixtures("mock_setup_entry", "mock_wled")
async def test_migrate_entry_v1_with_ignored_duplicates(
    hass: HomeAssistant, config_entry_v1: MockConfigEntry
) -> None:
    """Remove ignored entries with the same MAC and then migrate."""
    config_entry_v1.add_to_hass(hass)

    ignored_1 = MockConfigEntry(
        domain=DOMAIN,
        title="Ignored 1",
        unique_id="aabbccddeeff",
        source=SOURCE_IGNORE,
        version=1,
        minor_version=0,
        data={"host": "wled-ignored-1.local"},
    )
    ignored_2 = MockConfigEntry(
        domain=DOMAIN,
        title="Ignored 2",
        unique_id="aabbccddeeff",
        source=SOURCE_IGNORE,
        version=1,
        minor_version=0,
        data={"host": "wled-ignored-2.local"},
    )

    ignored_1.add_to_hass(hass)
    ignored_2.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry_v1.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert config_entry_v1.state == ConfigEntryState.LOADED
    assert config_entry_v1.version == 1
    assert config_entry_v1.minor_version == 2
    assert config_entry_v1.unique_id == "aabbccddeeff"

    assert ignored_1.state is ConfigEntryState.NOT_LOADED
    assert ignored_2.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_setup_entry", "mock_wled")
async def test_migrate_entry_v1_with_non_ignored_duplicate_aborts(
    hass: HomeAssistant,
    config_entry_v1: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Abort migration when there is another non-ignored entry with the same MAC."""
    config_entry_v1.add_to_hass(hass)

    duplicate_active = MockConfigEntry(
        domain=DOMAIN,
        title="Active duplicate",
        unique_id="aabbccddeeff",
        version=1,
        minor_version=0,
        data={"host": "wled-duplicate.local"},
    )
    duplicate_active.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry_v1.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert config_entry_v1.state == ConfigEntryState.MIGRATION_ERROR
    assert config_entry_v1.version == 1
    assert config_entry_v1.minor_version == 1
    assert config_entry_v1.unique_id == "AABBCCDDEEFF"
    assert "multiple WLED config entries with the same MAC address" in caplog.text


@pytest.mark.usefixtures("mock_setup_entry", "mock_wled")
async def test_migrate_entry_already_at_1_2_is_noop(
    hass: HomeAssistant,
) -> None:
    """Do nothing when entry is already at version 1.2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="WLED Already 1.2",
        unique_id="aabbccddeeff",
        version=1,
        minor_version=2,
        data={"host": "wled.local"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert entry.state == ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.unique_id == "aabbccddeeff"
