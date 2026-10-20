"""Tests for setting up the Meraki integration."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import api_error, setup_integration


async def test_load_unload(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client is closed when the entry is unloaded."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_meraki_client.__aexit__.assert_awaited_once()


async def test_client_closed_on_stop(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the client is closed when Home Assistant stops."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    mock_meraki_client.__aexit__.assert_awaited_once()


@pytest.mark.parametrize(
    ("status", "state"),
    [
        pytest.param(401, ConfigEntryState.SETUP_ERROR, id="invalid_auth"),
        pytest.param(503, ConfigEntryState.SETUP_RETRY, id="cannot_connect"),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    status: int,
    state: ConfigEntryState,
) -> None:
    """Test API errors during setup."""
    mock_meraki_client.organizations.getOrganizationNetworks.side_effect = api_error(
        status
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is state


async def test_invalid_auth_starts_reauth(
    hass: HomeAssistant,
    mock_meraki_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an API key that stopped working asks for a new one."""
    mock_meraki_client.organizations.getOrganizationNetworks.side_effect = api_error(
        401
    )
    await setup_integration(hass, mock_config_entry)
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]
