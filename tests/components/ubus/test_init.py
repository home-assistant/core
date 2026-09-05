"""Tests for the OpenWrt (ubus) integration setup."""

from unittest.mock import MagicMock

import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MAC_LAPTOP, MAC_PHONE

from tests.common import MockConfigEntry


async def test_setup_retry_on_connection_error(
    hass: HomeAssistant, mock_ubus: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry retries setup when the router is unreachable."""
    mock_ubus.return_value.connect.side_effect = TypeError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "connect",
    [
        pytest.param({"side_effect": PermissionError}, id="access_denied"),
        pytest.param({"side_effect": None, "return_value": None}, id="no_session"),
    ],
)
async def test_setup_error_on_invalid_credentials(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    connect: dict,
) -> None:
    """Test invalid credentials fail setup and start a reauth flow."""
    mock_ubus.return_value.connect.configure_mock(**connect)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_setup_retry_when_session_stays_denied(
    hass: HomeAssistant, mock_ubus: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup retries when the session is denied even after re-login."""
    mock_ubus.return_value.get_hostapd_clients.side_effect = PermissionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_ubus.return_value.connect.call_count == 2


async def test_session_refreshed_after_permission_error(
    hass: HomeAssistant,
    mock_ubus: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a dropped session is re-authenticated and the scan retried."""
    mock_ubus.return_value.get_hostapd_clients.side_effect = [
        PermissionError,
        {
            "clients": {
                MAC_PHONE: {"authorized": True},
                MAC_LAPTOP: {"authorized": True},
            }
        },
    ]

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_ubus.return_value.connect.call_count == 2
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {e.unique_id for e in entries} == {MAC_PHONE, MAC_LAPTOP}


async def test_unload_entry(
    hass: HomeAssistant, mock_ubus: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry unloads cleanly."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
