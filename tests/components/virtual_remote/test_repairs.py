"""Tests for Virtual Remote repair helpers."""

from homeassistant.components.virtual_remote.const import (
    DOMAIN,
    ISSUE_LINKED_INFRARED_ENTITY_MISSING,
)
from homeassistant.components.virtual_remote.repairs import (
    async_create_linked_infrared_entity_missing_issue,
    async_delete_linked_infrared_entity_missing_issue,
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
