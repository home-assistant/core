"""Tests for Husqvarna Automower repairs."""

from unittest.mock import AsyncMock

from aioautomower.exceptions import AuthError
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.husqvarna_automower.const import (
    DOMAIN,
    MIGRATION_AUTH_ISSUE_ID_PREFIX,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_migration_repair_starts_reauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_automower_client: AsyncMock,
    legacy_mock_config_entry: MockConfigEntry,
) -> None:
    """Test the migration repair starts OAuth reauthentication."""
    assert await async_setup_component(hass, "repairs", {})
    mock_automower_client.get_status.side_effect = AuthError
    legacy_mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(legacy_mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert legacy_mock_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    issue_id = f"{MIGRATION_AUTH_ISSUE_ID_PREFIX}{legacy_mock_config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, result["flow_id"], json={})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    reauth_flows = hass.config_entries.flow.async_progress()
    assert len(reauth_flows) == 1
    assert reauth_flows[0]["context"]["source"] == "reauth"
