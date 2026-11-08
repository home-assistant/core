"""Tests for the Fitbit integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.fitbit import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IGNORE,
    ConfigEntryDisabler,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


async def test_fitbit_repair_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the Fitbit config entry loading/unloading handles repair."""
    config_entry_1 = MockConfigEntry(
        title="Example 1",
        domain=DOMAIN,
    )
    config_entry_1.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_1.entry_id)
    await hass.async_block_till_done()
    assert config_entry_1.state is ConfigEntryState.LOADED

    config_entry_2 = MockConfigEntry(
        title="Example 2",
        domain=DOMAIN,
    )
    config_entry_2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()

    assert config_entry_2.state is ConfigEntryState.LOADED
    issue = issue_registry.async_get_issue(DOMAIN, DOMAIN)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.translation_key == "integration_removed"

    config_entry_3 = MockConfigEntry(
        source=SOURCE_IGNORE,
        domain=DOMAIN,
    )
    config_entry_3.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_3.entry_id)
    await hass.async_block_till_done()

    assert config_entry_3.state is ConfigEntryState.NOT_LOADED

    config_entry_4 = MockConfigEntry(
        disabled_by=ConfigEntryDisabler.USER,
        domain=DOMAIN,
    )
    config_entry_4.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_4.entry_id)
    await hass.async_block_till_done()

    assert config_entry_4.state is ConfigEntryState.NOT_LOADED

    await hass.config_entries.async_remove(config_entry_1.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(config_entry_1.entry_id) is None
    assert config_entry_2.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN) is not None

    await hass.config_entries.async_remove(config_entry_2.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_get_entry(config_entry_2.entry_id) is None
    assert issue_registry.async_get_issue(DOMAIN, DOMAIN) is None
    assert not hass.config_entries.async_entries(DOMAIN)
