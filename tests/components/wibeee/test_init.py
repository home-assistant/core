"""Tests for Wibeee integration setup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import aiohttp

from homeassistant import config_entries
from homeassistant.components.wibeee.const import (
    CONF_MAC_ADDRESS,
    CONF_UPDATE_MODE,
    CONF_WIBEEE_ID,
    DOMAIN,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_flow_init(hass: HomeAssistant) -> None:
    """Test that the flow is initialized."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM


async def test_config_entry_loaded(loaded_entry: ConfigEntry) -> None:
    """Test that config entry is loaded."""
    assert loaded_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test setup raises ConfigEntryNotReady on connection error."""
    mock_wibeee_api.async_fetch_device_info.side_effect = aiohttp.ClientError("boom")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_device_info_none_uses_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test setup uses fallback device info when API returns None."""
    # Force polling mode so we don't need push receiver IP resolution
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_UPDATE_MODE: MODE_POLLING}
    )
    mock_wibeee_api.async_fetch_device_info.return_value = None

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_push_mode_initial_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test push mode raises ConfigEntryNotReady when initial fetch fails."""
    mock_wibeee_api.async_fetch_sensors_data.side_effect = TimeoutError("timeout")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_push_mode_no_initial_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test push mode raises ConfigEntryNotReady when initial data is empty."""
    mock_wibeee_api.async_fetch_sensors_data.return_value = {}

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_push_mode_resolves_hostname(
    hass: HomeAssistant,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test push mode resolves hostname to IP via gethostbyname."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="001ec0112233",
        title="Wibeee 2233",
        data={
            CONF_HOST: "wibeee.local",
            CONF_MAC_ADDRESS: "001ec0112233",
            CONF_WIBEEE_ID: "WIBEEE",
        },
        options={CONF_UPDATE_MODE: MODE_LOCAL_PUSH},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wibeee.socket.gethostbyname",
        return_value="192.168.1.123",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_push_mode_hostname_resolution_fails(
    hass: HomeAssistant,
    mock_wibeee_api: MagicMock,
) -> None:
    """Test push mode raises ConfigEntryNotReady when hostname cannot be resolved."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="001ec0112233",
        title="Wibeee 2233",
        data={
            CONF_HOST: "invalid-hostname",
            CONF_MAC_ADDRESS: "001ec0112233",
            CONF_WIBEEE_ID: "WIBEEE",
        },
        options={CONF_UPDATE_MODE: MODE_LOCAL_PUSH},
        version=2,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.wibeee.socket.gethostbyname",
        side_effect=OSError("name resolution failed"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test that unloading works."""
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_options_update_reloads_entry(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
) -> None:
    """Test that updating options reloads the entry."""
    hass.config_entries.async_update_entry(
        loaded_entry, options={CONF_UPDATE_MODE: MODE_POLLING}
    )
    await hass.async_block_till_done()
    assert loaded_entry.state is ConfigEntryState.LOADED
    assert loaded_entry.options[CONF_UPDATE_MODE] == MODE_POLLING
