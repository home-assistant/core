"""Test the Blink services."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.blink.const import DOMAIN, SERVICE_SEND_PIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry

CAMERA_NAME = "Camera 1"
FILENAME = "blah"
PIN = "1234"


async def test_pin_service_calls(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pin service calls."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_blink_api.refresh.call_count == 1

    issue_registry = ir.async_get(hass)

    # Service should always raise an exception and create a repair issue
    with pytest.raises(
        HomeAssistantError, match="The service blink.send_pin has been removed"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            {ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id], CONF_PIN: PIN},
            blocking=True,
        )

    # Verify repair issue was created
    issues = issue_registry.issues
    assert len(issues) == 1
    issue = next(iter(issues.values()))
    assert issue.issue_id == "service_send_pin_deprecation"
    assert issue.domain == DOMAIN

    # Service should still raise error with bad config ID
    with pytest.raises(
        HomeAssistantError, match="The service blink.send_pin has been removed"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            {ATTR_CONFIG_ENTRY_ID: ["bad-config_id"], CONF_PIN: PIN},
            blocking=True,
        )


async def test_service_pin_creates_repair_issue(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the send PIN service creates a repair issue."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)

    # Initially no issues
    assert len(issue_registry.issues) == 0

    # Call the service (should fail but create repair issue)
    with pytest.raises(
        HomeAssistantError, match="The service blink.send_pin has been removed"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            {ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id], CONF_PIN: PIN},
            blocking=True,
        )

    # Verify repair issue was created
    issues = issue_registry.issues
    assert len(issues) == 1
    issue = next(iter(issues.values()))
    assert issue.issue_id == "service_send_pin_deprecation"
    assert issue.domain == DOMAIN
    assert issue.severity == ir.IssueSeverity.ERROR
    assert not issue.is_fixable

    # Call service again - should not create duplicate issue
    with pytest.raises(
        HomeAssistantError, match="The service blink.send_pin has been removed"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEND_PIN,
            {ATTR_CONFIG_ENTRY_ID: [mock_config_entry.entry_id], CONF_PIN: PIN},
            blocking=True,
        )

    # Still only one issue
    assert len(issue_registry.issues) == 1
