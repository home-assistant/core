"""Tests for the Elk-M1 Control utils."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.elkm1.const import DOMAIN
from homeassistant.components.elkm1.util import deprecate_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

ISSUE_ID = "deprecated_sensor_elkm1_setting_1"


async def test_deprecate_entity_issue_linked_to_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the deprecation issue is linked to and removed with the entry."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        "elkm1_setting_1",
        config_entry=config_entry,
    )

    assert deprecate_entity(
        hass,
        config_entry.entry_id,
        entity_registry,
        Platform.SENSOR,
        "elkm1_setting_1",
        ISSUE_ID,
        "deprecated_sensor",
        "elkm1_setting_1",
        "number.elkm1_setting_1",
    )
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.config_entry_id == config_entry.entry_id

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
