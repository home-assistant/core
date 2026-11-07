"""Test the Blink switch platform."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

ENTITY_ID = "switch.camera_1_camera_motion_detection"


@pytest.mark.parametrize(
    ("initial_enabled", "service", "expected_enabled", "expected_state"),
    [
        pytest.param(False, SERVICE_TURN_ON, True, STATE_ON, id="turn_on"),
        pytest.param(True, SERVICE_TURN_OFF, False, STATE_OFF, id="turn_off"),
    ],
)
async def test_motion_state_updates_when_refresh_is_skipped(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    camera: MagicMock,
    initial_enabled: bool,
    service: str,
    expected_enabled: bool,
    expected_state: str,
) -> None:
    """Test the new motion state shows straight away when BlinkPy skips the refresh."""
    camera.motion_enabled = initial_enabled

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    assert hass.states.get(ENTITY_ID).state == expected_state
    camera.async_arm.assert_awaited_once_with(expected_enabled)
