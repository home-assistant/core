"""Tests for the deprecation of the openSenseMap air quality entity."""

import pytest

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_DOMAIN
from homeassistant.components.automation import DOMAIN as AUTOMATION_DOMAIN
from homeassistant.components.opensensemap.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import TEST_STATION_ID

from tests.common import MockConfigEntry

ENTITY_ID = "air_quality.test_station"


def _register_air_quality_entity(
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    *,
    disabled: bool,
) -> str:
    """Register a pre-existing air quality entity and return its entity_id."""
    entry = entity_registry.async_get_or_create(
        AIR_QUALITY_DOMAIN,
        DOMAIN,
        TEST_STATION_ID,
        suggested_object_id="test_station",
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER if disabled else None,
    )
    assert entry.entity_id == ENTITY_ID
    return entry.entity_id


async def _setup_automation(hass: HomeAssistant, entity_id: str) -> None:
    """Set up an automation referencing an entity."""
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: {
                "alias": "test_automation",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {"action": "notify.notify", "data": {}},
            }
        },
    )


@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_air_quality_not_created_on_fresh_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the deprecated air quality entity is not created for new installations."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None
    assert entity_registry.async_get(ENTITY_ID) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"deprecated_air_quality_{mock_config_entry.entry_id}"
        )
        is None
    )


@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_air_quality_kept_when_enabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an existing, enabled air quality entity is kept and raises an issue."""
    mock_config_entry.add_to_hass(hass)
    _register_air_quality_entity(entity_registry, mock_config_entry, disabled=False)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is not None
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_air_quality_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_air_quality"


@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_air_quality_removed_when_disabled_and_unused(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a disabled, unused air quality entity is removed without an issue."""
    mock_config_entry.add_to_hass(hass)
    _register_air_quality_entity(entity_registry, mock_config_entry, disabled=True)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(ENTITY_ID) is None
    assert hass.states.get(ENTITY_ID) is None
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"deprecated_air_quality_{mock_config_entry.entry_id}"
        )
        is None
    )


@pytest.mark.parametrize(
    ("disabled", "state_present"),
    [
        pytest.param(False, True, id="enabled"),
        pytest.param(True, False, id="disabled"),
    ],
)
@pytest.mark.usefixtures("mock_opensensemap_api")
async def test_air_quality_issue_when_used(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    disabled: bool,
    state_present: bool,
) -> None:
    """Test an air quality entity used in automations is kept and flagged in use."""
    mock_config_entry.add_to_hass(hass)
    _register_air_quality_entity(entity_registry, mock_config_entry, disabled=disabled)
    await _setup_automation(hass, ENTITY_ID)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(ENTITY_ID) is not None
    assert (hass.states.get(ENTITY_ID) is not None) == state_present
    issue = issue_registry.async_get_issue(
        DOMAIN, f"deprecated_air_quality_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "deprecated_air_quality_in_use"
