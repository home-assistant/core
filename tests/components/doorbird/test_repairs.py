"""Test repairs for doorbird."""

from __future__ import annotations

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import mock_not_found_exception
from .conftest import DoorbirdMockerType

from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


async def test_change_schedule_fails(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a doorbird when change_schedule fails."""
    assert await async_setup_component(hass, "repairs", {})
    doorbird_entry = await doorbird_mocker(
        favorites_side_effect=mock_not_found_exception()
    )
    assert doorbird_entry.entry.state is ConfigEntryState.SETUP_RETRY
    issue_reg = ir.async_get(hass)
    assert len(issue_reg.issues) == 1
    issue = list(issue_reg.issues.values())[0]
    issue_id = issue.issue_id
    assert issue.domain == DOMAIN

    await async_process_repairs_platforms(hass)
    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = data["flow_id"]
    placeholders = data["description_placeholders"]
    assert "404" in placeholders["error"]
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, flow_id)

    assert data["type"] == "create_entry"
