"""Tests for the P1 Monitor integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from p1monitor import P1MonitorConnectionError
from syrupy import SnapshotAssertion

from homeassistant.components.p1_monitor.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_p1monitor: AsyncMock
) -> None:
    """Test the P1 Monitor configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@patch(
    "homeassistant.components.p1_monitor.coordinator.P1Monitor._request",
    side_effect=P1MonitorConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the P1 Monitor configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migration(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test config entry version 1 -> 2 migration."""
    mock_config_entry = MockConfigEntry(
        unique_id="unique_thingy",
        domain=DOMAIN,
        data={CONF_HOST: "example"},
        version=1,
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(mock_config_entry.entry_id) == snapshot


async def test_port_migration(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test migration of host:port to separate host and port."""
    mock_config_entry = MockConfigEntry(
        unique_id="unique_thingy",
        domain=DOMAIN,
        data={CONF_HOST: "example:80"},
        version=1,
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(mock_config_entry.entry_id) == snapshot
