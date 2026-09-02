"""Tests for the Community store repairs."""

from homeassistant.components.store.base import HacsBase
from homeassistant.components.store.const import DOMAIN
from homeassistant.components.store.repairs import async_create_fix_flow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import REPOSITORY_INTEGRATION_ID

from tests.common import async_mock_service
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

ISSUE_ID = f"restart_required_{REPOSITORY_INTEGRATION_ID}_1.0.0"


async def test_restart_required_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    store: HacsBase,
) -> None:
    """Test restarting Home Assistant from the repair."""
    assert await async_setup_component(hass, "repairs", {})
    restarts = async_mock_service(hass, "homeassistant", "restart")

    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="restart_required",
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    assert data["step_id"] == "confirm_restart"
    assert data["description_placeholders"] == {"name": "Basic integration"}

    data = await process_repair_fix_flow(client, data["flow_id"])

    assert data["type"] == "create_entry"
    assert len(restarts) == 1
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_restart_required_fix_flow_for_an_unknown_repository(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, store: HacsBase
) -> None:
    """Test the repair of a repository the store no longer knows."""
    assert await async_setup_component(hass, "repairs", {})
    issue_id = "restart_required_0_1.0.0"

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="restart_required",
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    assert data["step_id"] == "confirm_restart"
    assert data["description_placeholders"] == {"name": ""}


async def test_no_fix_flow_for_other_issues(hass: HomeAssistant) -> None:
    """Test that only the restart issue is fixable."""
    assert await async_create_fix_flow(hass, "removed_1296269", None) is None
