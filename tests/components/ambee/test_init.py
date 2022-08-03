"""Tests for the Ambee integration."""
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientWebSocketResponse
from ambee import AmbeeConnectionError
from ambee.exceptions import AmbeeAuthenticationError
import pytest

from homeassistant.components.ambee.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.repairs import get_repairs


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ambee: AsyncMock,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test the Ambee configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "pending_removal"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 0

    assert not hass.data.get(DOMAIN)


@patch(
    "homeassistant.components.ambee.Ambee.request",
    side_effect=AmbeeConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Ambee configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("service_name", ["air_quality", "pollen"])
async def test_config_entry_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ambee: MagicMock,
    service_name: str,
) -> None:
    """Test the Ambee configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)

    service = getattr(mock_ambee.return_value, service_name)
    service.side_effect = AmbeeAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
