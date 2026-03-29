"""Tests for UniFi Access repairs."""

from __future__ import annotations

from unittest.mock import MagicMock

from unifi_access_api import ApiAuthError

from homeassistant.components.unifi_access.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import async_get as async_get_issue_registry
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_api_token_expired_creates_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that an expired API token creates a repair issue."""
    mock_client.authenticate.side_effect = ApiAuthError()
    await setup_integration(hass, mock_config_entry)

    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = next(
        i for i in msg["result"]["issues"] if i["issue_id"] == "api_token_expired"
    )
    assert issue["is_fixable"] is True
    assert issue["severity"] == "error"
    assert issue["translation_key"] == "api_token_expired"


async def test_api_token_expired_repair_flow_triggers_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that the repair flow triggers reauthentication."""
    mock_client.authenticate.side_effect = ApiAuthError()
    await setup_integration(hass, mock_config_entry)

    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, "api_token_expired")
    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)
    assert data["type"] == "create_entry"

    await hass.async_block_till_done()
    assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_successful_setup_clears_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that a successful setup clears the repair issue."""
    # First, trigger the repair issue with an auth error
    mock_client.authenticate.side_effect = ApiAuthError()
    await setup_integration(hass, mock_config_entry)

    issue_registry = async_get_issue_registry(hass)
    assert issue_registry.async_get_issue(DOMAIN, "api_token_expired") is not None

    # Now simulate successful reauth by clearing the error and reloading
    mock_client.authenticate.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "api_token_expired") is None
