"""Tests for the LIFX repairs flows."""

from unittest.mock import patch

import pytest

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.lifx.const import DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import async_setup_lifx_entry
from .helpers import (
    INFRARED_NUMBER_ENTITY_ID,
    INFRARED_SELECT_ENTITY_ID,
    create_mock_infrared_light,
    register_legacy_infrared_select,
)

from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

ISSUE_ID = f"deprecated_infrared_select_{INFRARED_SELECT_ENTITY_ID}"
REGISTERED_AUTOMATION_ENTITY_ID = "automation.night_vision"


async def _async_setup_deprecated_select(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Set up a device whose infrared select is deprecated and fixable."""
    register_legacy_infrared_select(entity_registry)
    await async_setup_lifx_entry(hass, create_mock_infrared_light())
    assert await async_setup_component(hass, "repairs", {})


async def test_fixing_the_deprecated_select_removes_it(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test confirming the fix removes the select and closes the issue."""
    await _async_setup_deprecated_select(hass, entity_registry)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "entity_id": INFRARED_SELECT_ENTITY_ID,
        "entity_name": "Infrared brightness",
        "replacement_entity_id": INFRARED_NUMBER_ENTITY_ID,
    }

    result = await process_repair_fix_flow(client, result["flow_id"])

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entity_registry.async_get(INFRARED_SELECT_ENTITY_ID) is None
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


@pytest.mark.parametrize(
    ("used_by", "expected_used_by"),
    [
        pytest.param(
            [REGISTERED_AUTOMATION_ENTITY_ID],
            "- [Night vision](/config/automation/edit/night_vision)",
            id="registered-automation",
        ),
        pytest.param(
            ["automation.not_registered"],
            "- `automation.not_registered`",
            id="unregistered-automation",
        ),
    ],
)
async def test_fixing_a_select_that_is_now_in_use_is_aborted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    used_by: list[str],
    expected_used_by: str,
) -> None:
    """Test a select an automation started using is kept and the user told which."""
    await _async_setup_deprecated_select(hass, entity_registry)
    entity_registry.async_get_or_create(
        AUTOMATION_DOMAIN,
        AUTOMATION_DOMAIN,
        "night_vision",
        suggested_object_id="night_vision",
        original_name="Night vision",
    )
    client = await hass_client()

    with patch(
        "homeassistant.components.lifx.repairs.automations_with_entity",
        return_value=used_by,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "in_use"
    assert result["description_placeholders"] == {
        "entity_id": INFRARED_SELECT_ENTITY_ID,
        "entity_name": "Infrared brightness",
        "replacement_entity_id": INFRARED_NUMBER_ENTITY_ID,
        "used_by": expected_used_by,
    }
    assert entity_registry.async_get(INFRARED_SELECT_ENTITY_ID) is not None
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None


async def test_fixing_a_select_a_script_uses_is_aborted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a script referencing the select blocks the fix just as an automation does."""
    await _async_setup_deprecated_select(hass, entity_registry)
    entity_registry.async_get_or_create(
        SCRIPT_DOMAIN,
        SCRIPT_DOMAIN,
        "night_vision",
        suggested_object_id="night_vision",
        original_name="Night vision",
    )
    client = await hass_client()

    with patch(
        "homeassistant.components.lifx.repairs.scripts_with_entity",
        return_value=["script.night_vision"],
    ):
        result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "in_use"
    assert (
        result["description_placeholders"]["used_by"]
        == "- [Night vision](/config/script/edit/night_vision)"
    )
    assert entity_registry.async_get(INFRARED_SELECT_ENTITY_ID) is not None


async def test_fixing_an_already_removed_select_is_aborted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a select removed while the issue was open aborts the fix."""
    await _async_setup_deprecated_select(hass, entity_registry)
    entity_registry.async_remove(INFRARED_SELECT_ENTITY_ID)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_removed"
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
