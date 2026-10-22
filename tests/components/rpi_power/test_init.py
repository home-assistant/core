"""Tests for rpi_power integration."""

from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry, patch

from homeassistant.components.rpi_power.const import DOMAIN, ISSUE_UNDER_VOLTAGE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


async def test_entry_setup_unload(hass: HomeAssistant) -> None:
    """Test integration setup and unload."""

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.rpi_power.new_under_voltage", get=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_error(hass: HomeAssistant) -> None:
    """Test config entry error."""
    with patch(
        "homeassistant.components.rpi_power.new_under_voltage", return_value=None
    ):
        config_entry = MockConfigEntry(domain=DOMAIN)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


def _create_unlinked_issue(hass: HomeAssistant) -> None:
    """Create the issue as it was raised before issues were linked to entries."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_UNDER_VOLTAGE,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.CRITICAL,
        translation_key=ISSUE_UNDER_VOLTAGE,
    )


async def test_unlinked_issue_linked_on_setup(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test setup links an issue raised before it was linked to the entry."""
    _create_unlinked_issue(hass)
    issue_registry.async_ignore(DOMAIN, ISSUE_UNDER_VOLTAGE, True)
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rpi_power.new_under_voltage",
        return_value=MagicMock(get=MagicMock(return_value=False)),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_UNDER_VOLTAGE)
    assert issue is not None
    assert issue.config_entry_id == config_entry.entry_id
    assert issue.dismissed_version is not None


async def test_unlinked_issue_removed_with_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test removing an entry that never set up deletes its unlinked issue."""
    _create_unlinked_issue(hass)
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_UNDER_VOLTAGE) is None
