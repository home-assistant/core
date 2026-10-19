"""Test the Antifurto365 iAlarm alarm control panel."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyasyncialarm import IAlarm
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.components.ialarm.coordinator import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

ENTITY_ID = "alarm_control_panel.ialarm"


async def _setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        (IAlarm.ARMED_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (IAlarm.ARMED_STAY, AlarmControlPanelState.ARMED_HOME),
        (IAlarm.DISARMED, AlarmControlPanelState.DISARMED),
        (IAlarm.TRIGGERED, AlarmControlPanelState.TRIGGERED),
        (IAlarm.CANCEL, STATE_UNKNOWN),
    ],
)
async def test_state(
    hass: HomeAssistant,
    ialarm_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    status: int,
    expected_state: str,
) -> None:
    """Test the panel status is mapped to the entity state."""
    ialarm_api.return_value.get_status.return_value = {
        "status_value": status,
        "alarmed_zones": [],
    }
    await _setup(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected_state


@pytest.mark.parametrize("side_effect", [ConnectionError, TimeoutError])
async def test_unavailable_on_connection_error(
    hass: HomeAssistant,
    ialarm_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception],
) -> None:
    """Test the entity becomes unavailable when the panel cannot be reached."""
    await _setup(hass, mock_config_entry)

    ialarm_api.return_value.get_status.side_effect = side_effect
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_ALARM_ARM_AWAY, "arm_away"),
        (SERVICE_ALARM_ARM_HOME, "arm_stay"),
        (SERVICE_ALARM_DISARM, "disarm"),
    ],
)
async def test_actions(
    hass: HomeAssistant,
    ialarm_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test the alarm actions send the matching command to the panel."""
    await _setup(hass, mock_config_entry)

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    getattr(ialarm_api.return_value, method).assert_awaited_once()
