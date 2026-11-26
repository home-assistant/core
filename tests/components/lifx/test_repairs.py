"""Tests for LIFX repairs."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.lifx import DOMAIN
from homeassistant.components.script import DOMAIN as SCRIPT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import IP_ADDRESS, LABEL, async_setup_lifx_entry
from .helpers import (
    INFRARED_NUMBER_ENTITY_ID,
    INFRARED_SELECT_ENTITY_ID,
    create_mock_infrared_light,
    register_legacy_infrared_select,
)

MALFORMED_UNIQUE_ID = "gg:bb:cc:dd:ee:cc"
RENAMED_SELECT_ENTITY_ID = "select.night_vision_level"
RENAMED_NUMBER_ENTITY_ID = "number.night_vision_level"


async def _setup_malformed_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry whose stored serial cannot be migrated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen",
        version=1,
        unique_id=MALFORMED_UNIQUE_ID,
        data={CONF_HOST: IP_ADDRESS},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    return entry


async def test_invalid_serial_fix_flow_removes_entry(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the invalid serial repair removes the entry it was raised for."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await _setup_malformed_entry(hass)
    issue_id = f"invalid_serial_{entry.entry_id}"

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == entry.entry_id
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_placeholders == {
        "title": "Kitchen",
        "unique_id": MALFORMED_UNIQUE_ID,
    }

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, data["flow_id"])
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_removing_entry_deletes_invalid_serial_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test deleting the entry by hand also clears its repair issue."""
    entry = await _setup_malformed_entry(hass)
    issue_id = f"invalid_serial_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_invalid_serial_fix_flow_entry_already_removed(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test confirming the repair after the entry was deleted by hand."""
    assert await async_setup_component(hass, "repairs", {})
    entry = await _setup_malformed_entry(hass)
    issue_id = f"invalid_serial_{entry.entry_id}"

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    data = await process_repair_fix_flow(client, data["flow_id"])

    assert data["type"] == "create_entry"


async def _setup_deprecated_select(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> str:
    """Set up a device that still has the infrared select and return its issue."""
    assert await async_setup_component(hass, "repairs", {})
    register_legacy_infrared_select(entity_registry)
    entry = await async_setup_lifx_entry(hass, create_mock_infrared_light())
    return f"deprecated_infrared_select_{entry.entry_id}"


@pytest.mark.parametrize(
    ("entity_id", "number_entity_id"),
    [
        pytest.param(
            INFRARED_SELECT_ENTITY_ID, INFRARED_NUMBER_ENTITY_ID, id="original"
        ),
        pytest.param(
            RENAMED_SELECT_ENTITY_ID,
            RENAMED_NUMBER_ENTITY_ID,
            id="renamed-after-the-issue",
        ),
    ],
)
async def test_deprecated_infrared_select_fix_flow_removes_select(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    entity_id: str,
    number_entity_id: str,
) -> None:
    """Test confirming the repair removes the select and names the current number."""
    issue_id = await _setup_deprecated_select(hass, entity_registry)
    entity_registry.async_update_entity(
        INFRARED_SELECT_ENTITY_ID, new_entity_id=entity_id
    )
    entity_registry.async_update_entity(
        INFRARED_NUMBER_ENTITY_ID, new_entity_id=number_entity_id
    )
    await hass.async_block_till_done()
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {
        "device_name": LABEL,
        "entity_id": entity_id,
        "replacement_entity_id": number_entity_id,
    }

    result = await process_repair_fix_flow(client, result["flow_id"])

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entity_registry.async_get(entity_id) is None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert hass.states.get(number_entity_id) is not None


@pytest.mark.parametrize(
    ("used_by_function", "used_by", "registered_domain", "expected_used_by"),
    [
        pytest.param(
            "automations_with_entity",
            ["automation.night_vision"],
            AUTOMATION_DOMAIN,
            "- [Night vision](/config/automation/edit/night_vision)",
            id="registered-automation",
        ),
        pytest.param(
            "scripts_with_entity",
            ["script.night_vision"],
            SCRIPT_DOMAIN,
            "- [Night vision](/config/script/edit/night_vision)",
            id="registered-script",
        ),
        pytest.param(
            "automations_with_entity",
            ["automation.not_registered"],
            AUTOMATION_DOMAIN,
            "- `automation.not_registered`",
            id="unregistered-automation",
        ),
    ],
)
async def test_deprecated_infrared_select_fix_flow_keeps_a_select_in_use(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    used_by_function: str,
    used_by: list[str],
    registered_domain: str,
    expected_used_by: str,
) -> None:
    """Test a select an automation or script uses is kept and the user told which."""
    issue_id = await _setup_deprecated_select(hass, entity_registry)
    entity_registry.async_get_or_create(
        registered_domain,
        registered_domain,
        "night_vision",
        suggested_object_id="night_vision",
        original_name="Night vision",
    )
    client = await hass_client()

    with patch(
        f"homeassistant.components.lifx.repairs.{used_by_function}",
        return_value=used_by,
    ):
        result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "in_use"
    assert result["description_placeholders"] == {
        "device_name": LABEL,
        "entity_id": INFRARED_SELECT_ENTITY_ID,
        "replacement_entity_id": INFRARED_NUMBER_ENTITY_ID,
        "used_by": expected_used_by,
    }
    assert entity_registry.async_get(INFRARED_SELECT_ENTITY_ID) is not None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_deprecated_infrared_select_fix_flow_select_already_removed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a select removed while the issue was open aborts and drops the issue."""
    issue_id = await _setup_deprecated_select(hass, entity_registry)
    entity_registry.async_remove(INFRARED_SELECT_ENTITY_ID)
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_removed"
    assert result["description_placeholders"] == {"device_name": LABEL}
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
