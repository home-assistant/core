"""Test repairs for doorbird."""

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import mock_not_found_exception
from .conftest import DoorbirdMockerType, patch_doorbird_api_entry_points

from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


async def test_change_schedule_fails(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    doorbird_mocker: DoorbirdMockerType,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a doorbird when change_schedule fails."""
    assert await async_setup_component(hass, "repairs", {})
    doorbird_entry = await doorbird_mocker(
        favorites_side_effect=mock_not_found_exception()
    )
    assert doorbird_entry.entry.state is ConfigEntryState.SETUP_RETRY
    assert len(issue_registry.issues) == 1
    issue = list(issue_registry.issues.values())[0]
    issue_id = issue.issue_id
    assert issue.domain == DOMAIN

    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    placeholders = data["description_placeholders"]
    assert "404" in placeholders["error"]
    assert data["step_id"] == "confirm"

    with patch_doorbird_api_entry_points(doorbird_entry.api):
        data = await process_repair_fix_flow(client, flow_id)
        await hass.async_block_till_done()

    assert data["type"] == "create_entry"
