"""Tests for the TOLO Sauna switches."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

ENTITY_ID = "switch.tolo_sauna_aroma_therapy"


@pytest.fixture(autouse=True)
def switch_platform_only() -> Generator[None]:
    """Only set up the switch platform."""
    with patch("homeassistant.components.tolo.PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.parametrize(
    ("initial_value", "service", "expected_value", "expected_state"),
    [
        pytest.param(False, SERVICE_TURN_ON, True, STATE_ON, id="turn_on"),
        pytest.param(True, SERVICE_TURN_OFF, False, STATE_OFF, id="turn_off"),
    ],
)
async def test_switch_state_updated_after_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tolo_client: MagicMock,
    initial_value: bool,
    service: str,
    expected_value: bool,
    expected_state: str,
) -> None:
    """Test the switch reflects the new state right after an action."""
    mock_tolo_client.get_status.return_value.aroma_therapy_on = initial_value
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The device reports the new state once the command has been sent.
    mock_tolo_client.get_status.return_value.aroma_therapy_on = expected_value
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )

    mock_tolo_client.set_aroma_therapy_on.assert_called_once_with(expected_value)
    assert hass.states.get(ENTITY_ID).state == expected_state
