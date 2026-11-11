"""Tests for the Holiday integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.holiday.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

MOCK_CONFIG_DATA = {
    "country": "Germany",
    "province": "BW",
}


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing integration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    state: ConfigEntryState = entry.state
    assert state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("data", "options", "issue", "placeholders"),
    [
        pytest.param(
            {"country": "XX"},
            {},
            "unsupported_country",
            {"country": "XX"},
            id="country",
        ),
        pytest.param(
            {"country": "DE", "province": "XX"},
            {},
            "unsupported_province",
            {"country": "DE", "province": "XX"},
            id="province",
        ),
        pytest.param(
            {"country": "DE", "province": "BW"},
            {"categories": ["bogus"]},
            "unsupported_categories",
            {"country": "DE", "categories": "bogus"},
            id="categories",
        ),
    ],
)
async def test_unsupported_configuration(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    data: dict[str, str],
    options: dict[str, list[str]],
    issue: str,
    placeholders: dict[str, str],
) -> None:
    """Test a configuration the holidays library no longer supports."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test", data=data, options=options)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == issue

    repair = issue_registry.async_get_issue(DOMAIN, f"{issue}_{entry.entry_id}")
    assert repair
    assert repair.translation_key == issue
    assert repair.translation_placeholders == {"title": "Test", **placeholders}


async def test_unsupported_configuration_issue_deleted(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the issue is deleted when the configuration is supported again."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG_DATA)
    entry.add_to_hass(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"unsupported_province_{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="unsupported_province",
        translation_placeholders={"title": "Test", "country": "DE", "province": "XX"},
        data={"entry_id": entry.entry_id, "issue": "unsupported_province"},
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert not issue_registry.async_get_issue(
        DOMAIN, f"unsupported_province_{entry.entry_id}"
    )
