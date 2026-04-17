"""Tests for the homeassistant_hardware repairs helpers."""

from __future__ import annotations

import pytest

from homeassistant.components.homeassistant_hardware.repairs import (
    ISSUE_MULTI_PAN_MIGRATION,
    async_create_multi_pan_migration_issue,
    async_delete_multi_pan_migration_issue,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

TEST_DOMAIN = "test_hardware"


@pytest.fixture
def ignore_translations_for_mock_domains() -> str:
    """Ignore translation check for the fake test_hardware domain."""
    return TEST_DOMAIN


async def test_create_and_delete_multi_pan_migration_issue(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test the helpers create and delete the migration issue per entry."""
    entry = MockConfigEntry(domain=TEST_DOMAIN, title="Test HW", data={})
    entry.add_to_hass(hass)

    async_create_multi_pan_migration_issue(hass, TEST_DOMAIN, entry)
    issue_id = f"{ISSUE_MULTI_PAN_MIGRATION}_{entry.entry_id}"
    issue = issue_registry.async_get_issue(domain=TEST_DOMAIN, issue_id=issue_id)
    assert issue is not None
    assert issue.translation_key == ISSUE_MULTI_PAN_MIGRATION
    assert issue.translation_placeholders == {"hardware_name": "Test HW"}
    assert issue.data == {"entry_id": entry.entry_id}
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.WARNING

    async_delete_multi_pan_migration_issue(hass, TEST_DOMAIN, entry)
    assert issue_registry.async_get_issue(domain=TEST_DOMAIN, issue_id=issue_id) is None
