"""Tests for the SmartyPlants repair issues."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.smartyplants.const import DOMAIN
from homeassistant.components.smartyplants.repairs import LEGACY_ENTITIES_ISSUE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

LEGACY_ENTITY_ID = "sensor.monstera_fertilise_in"


@pytest.fixture
async def repairs(hass: HomeAssistant) -> None:
    """Set up the repairs component."""
    assert await async_setup_component(hass, "repairs", {})


def _add_legacy_entry(
    entity_registry: er.EntityRegistry, entry: MockConfigEntry
) -> er.RegistryEntry:
    """Add the registry entry the custom integration would have left."""
    return entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "sensor-1_fertilise_days",
        config_entry=entry,
        suggested_object_id="monstera_fertilise_in",
    )


@pytest.mark.usefixtures("mock_smartyplants_client", "repairs")
async def test_no_issue_when_nothing_was_left_behind(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a clean install raises nothing."""
    await setup_integration(hass, mock_config_entry)

    assert not issue_registry.issues


@pytest.mark.usefixtures("mock_smartyplants_client", "repairs")
async def test_no_issue_when_the_entry_was_adopted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an adopted entry is not reported as a problem."""
    mock_config_entry.add_to_hass(hass)
    _add_legacy_entry(entity_registry, mock_config_entry)

    await setup_integration(hass, mock_config_entry)

    assert not issue_registry.issues


@pytest.mark.usefixtures("mock_smartyplants_client", "repairs")
async def test_issue_lists_the_stranded_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entry that could not be adopted is reported."""
    mock_config_entry.add_to_hass(hass)
    _add_legacy_entry(entity_registry, mock_config_entry)
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "sensor-1_fertilize",
        config_entry=mock_config_entry,
        suggested_object_id="monstera_fertilize_in",
    )

    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"{LEGACY_ENTITIES_ISSUE}_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable
    assert LEGACY_ENTITY_ID in issue.translation_placeholders["entities"]


@pytest.mark.usefixtures("mock_smartyplants_client", "repairs")
async def test_fix_flow_removes_the_stranded_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the fix deletes the leftover entity and clears the issue."""
    mock_config_entry.add_to_hass(hass)
    _add_legacy_entry(entity_registry, mock_config_entry)
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "sensor-1_fertilize",
        config_entry=mock_config_entry,
        suggested_object_id="monstera_fertilize_in",
    )
    await setup_integration(hass, mock_config_entry)

    issue_id = f"{LEGACY_ENTITIES_ISSUE}_{mock_config_entry.entry_id}"
    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, data["flow_id"])
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert entity_registry.async_get(LEGACY_ENTITY_ID) is None
    assert entity_registry.async_get("sensor.monstera_fertilize_in") is not None
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
