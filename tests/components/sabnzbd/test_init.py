"""Tests for the SABnzbd Integration."""

import pytest

from homeassistant.components.sabnzbd.const import (
    ATTR_API_KEY,
    DOMAIN,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_SPEED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


@pytest.mark.parametrize(
    ("service", "issue_id"),
    [
        (SERVICE_RESUME, "resume_action_deprecated"),
        (SERVICE_PAUSE, "pause_action_deprecated"),
        (SERVICE_SET_SPEED, "set_speed_action_deprecated"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_deprecated_service_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    service: str,
    issue_id: str,
) -> None:
    """Test that deprecated actions creates an issue."""
    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0"},
        blocking=True,
    )

    issue = issue_registry.async_get_issue(domain=DOMAIN, issue_id=issue_id)
    assert issue
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.breaks_in_ha_version == "2025.6"
