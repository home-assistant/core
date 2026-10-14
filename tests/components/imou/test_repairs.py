"""Tests for Imou repair issues."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.exceptions import ImouException
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.imou.const import DOMAIN
from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.components.imou.repairs import ISSUE_OPEN_API_QUOTA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry, async_fire_time_changed


def _quota_issue_id(entry_id: str) -> str:
    return f"{ISSUE_OPEN_API_QUOTA}_{entry_id}"


@pytest.mark.usefixtures("mock_imou_openapi_client", "mock_imou_ha_device_manager")
async def test_setup_quota_error_creates_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Listing devices with an exhausted quota creates a repair issue."""
    mock_imou_ha_device_manager.async_get_devices.side_effect = ImouException(
        "OP1013 monthly quota exceeded"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert issue_registry.async_get_issue(
        DOMAIN, _quota_issue_id(mock_config_entry.entry_id)
    )


@pytest.mark.usefixtures("init_integration")
async def test_successful_coordinator_refresh_clears_quota_repair(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A successful poll clears a previously raised quota repair issue."""
    issue_id = _quota_issue_id(mock_config_entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_OPEN_API_QUOTA,
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.usefixtures("init_integration")
async def test_entity_command_quota_creates_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An entity service call that hits the quota limit creates a repair issue."""
    mock_imou_ha_device_manager.async_press_button.side_effect = ImouException(
        "error OP1013"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.device_1_mute"},
            blocking=True,
        )

    assert issue_registry.async_get_issue(
        DOMAIN, _quota_issue_id(mock_config_entry.entry_id)
    )


@pytest.mark.usefixtures("init_integration")
async def test_unload_removes_quota_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Removing the config entry deletes the quota repair issue."""
    issue_id = _quota_issue_id(mock_config_entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_OPEN_API_QUOTA,
    )

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
