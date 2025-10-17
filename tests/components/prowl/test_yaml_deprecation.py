"""Tests for the migration from YAML to config entries."""

import prowlpy
import pytest

from homeassistant.components import notify
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import OTHER_API_KEY, TEST_API_KEY
from .helpers import get_config_entry

SERVICE_DATA = {"message": "Test Notification", "title": "Test Title"}


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_yaml_migration_creates_config_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that YAML configuration triggers config entry creation."""
    entry = get_config_entry(hass, TEST_API_KEY, config_method="import")

    assert entry is not None, "No import config entry found"
    assert entry.data[CONF_API_KEY] == TEST_API_KEY

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_prowl")

    assert issue is not None, "No issue found for YAML deprecation"
    assert issue.translation_key == "prowl_yaml_deprecated"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_yaml_migration_with_bad_key(hass: HomeAssistant, mock_prowlpy) -> None:
    """Test that YAML configuration with bad API key creates issue but no config entry."""
    mock_prowlpy.verify_key.side_effect = (
        prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}"),
    )

    await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "api_key": "invalid_key",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    entry = get_config_entry(hass, "invalid_key", config_method="import")
    assert entry is None, "Config entry should not be created with invalid API key"


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_yaml_migration_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that YAML configuration creates a repair issue."""
    issue = issue_registry.async_get_issue(DOMAIN, f"deprecated_yaml_{DOMAIN}")
    assert issue is not None
    assert issue.translation_key == "prowl_yaml_deprecated"
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_prowlpy")
async def test_yaml_migration_migrates_all_entries(
    hass: HomeAssistant,
) -> None:
    """Test that multiple YAML setups all get migrated."""
    await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "api_key": TEST_API_KEY,
                },
                {
                    "name": f"{DOMAIN}_2",
                    "platform": DOMAIN,
                    "api_key": OTHER_API_KEY,
                },
            ]
        },
    )
    await hass.async_block_till_done()
    entry = get_config_entry(hass, TEST_API_KEY, config_method="import")

    assert entry is not None, "First import config entry not found"
    assert entry.data[CONF_API_KEY] == TEST_API_KEY

    entry = get_config_entry(hass, OTHER_API_KEY, config_method="import")

    assert entry is not None, "Second import config entry not found"
    assert entry.data[CONF_API_KEY] == OTHER_API_KEY


async def test_yaml_migration_does_not_duplicate_config_entry(
    hass: HomeAssistant,
    mock_prowlpy_config_entry,
) -> None:
    """Test that we don't create duplicates when migrating YAML entities if there are existing ConfigEntries."""
    mock_prowlpy_config_entry.add_to_hass(hass)

    entries_before = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_API_KEY) == TEST_API_KEY
    ]

    await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "api_key": TEST_API_KEY,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    entries_after = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_API_KEY) == TEST_API_KEY
    ]
    assert len(entries_after) == len(entries_before)
    assert mock_prowlpy_config_entry in entries_after


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_legacy_notify_service_creates_migration_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that calling legacy notify service creates migration issue."""
    await hass.services.async_call(
        notify.DOMAIN,
        DOMAIN,
        SERVICE_DATA,
        blocking=True,
    )

    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(notify.DOMAIN, "migrate_notify_prowl_prowl")

    assert issue is not None
    assert issue.translation_key == "migrate_notify_service"
    assert issue.severity == ir.IssueSeverity.WARNING
