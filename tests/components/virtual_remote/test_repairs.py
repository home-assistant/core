"""Tests for Virtual Remote repair helpers."""

from homeassistant.components.virtual_remote.const import (
    DOMAIN,
    ISSUE_LINKED_INFRARED_ENTITY_MISSING,
)
from homeassistant.components.virtual_remote.repairs import (
    async_create_linked_infrared_entity_missing_issue,
    async_delete_linked_infrared_entity_missing_issue,
    async_delete_stale_linked_infrared_entity_missing_issues,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


def test_create_and_delete_missing_infrared_issue(hass: HomeAssistant) -> None:
    """Test missing linked infrared entity repair issue lifecycle."""
    issue_registry = ir.async_get(hass)

    async_create_linked_infrared_entity_missing_issue(
        hass,
        remote_id="living_room_tv",
        remote_name="Living Room TV",
        infrared_entity_id="infrared.missing",
    )

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"{ISSUE_LINKED_INFRARED_ENTITY_MISSING}_living_room_tv",
    )
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == ISSUE_LINKED_INFRARED_ENTITY_MISSING
    assert issue.translation_placeholders == {
        "remote_name": "Living Room TV",
        "infrared_entity_id": "infrared.missing",
    }

    async_delete_linked_infrared_entity_missing_issue(
        hass,
        remote_id="living_room_tv",
    )

    assert (
        issue_registry.async_get_issue(
            DOMAIN,
            f"{ISSUE_LINKED_INFRARED_ENTITY_MISSING}_living_room_tv",
        )
        is None
    )


def test_delete_stale_missing_infrared_issues(hass: HomeAssistant) -> None:
    """Test stale missing linked infrared entity repair issues are deleted."""
    issue_registry = ir.async_get(hass)

    async_create_linked_infrared_entity_missing_issue(
        hass,
        remote_id="keep",
        remote_name="Keep",
        infrared_entity_id="infrared.keep",
    )
    async_create_linked_infrared_entity_missing_issue(
        hass,
        remote_id="stale",
        remote_name="Stale",
        infrared_entity_id="infrared.stale",
    )

    async_delete_stale_linked_infrared_entity_missing_issues(
        hass, configured_remote_ids={"keep"}
    )

    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"{ISSUE_LINKED_INFRARED_ENTITY_MISSING}_keep"
        )
        is not None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"{ISSUE_LINKED_INFRARED_ENTITY_MISSING}_stale"
        )
        is None
    )
