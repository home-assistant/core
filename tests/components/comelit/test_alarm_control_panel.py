"""Tests for Comelit SimpleHome alarm control panel platform."""

from unittest.mock import AsyncMock

from aiocomelit.api import AlarmDataObject, ComelitVedoAreaObject, ComelitVedoZoneObject
from aiocomelit.const import AlarmAreaState, AlarmZoneState
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.alarm_control_panel import (
    ATTR_CODE,
    DOMAIN as ALARM_DOMAIN,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    AlarmControlPanelState,
)
from homeassistant.components.comelit.const import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import VEDO_PIN

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "alarm_control_panel.area0"


@pytest.mark.parametrize(
    ("human_status", "armed", "alarm_state"),
    [
        (AlarmAreaState.DISARMED, 0, AlarmControlPanelState.DISARMED),
        (AlarmAreaState.ARMED, 1, AlarmControlPanelState.ARMED_HOME),
        (AlarmAreaState.ARMED, 2, AlarmControlPanelState.ARMED_HOME),
        (AlarmAreaState.ARMED, 3, AlarmControlPanelState.ARMED_NIGHT),
        (AlarmAreaState.ARMED, 4, AlarmControlPanelState.ARMED_AWAY),
        (AlarmAreaState.UNKNOWN, 0, STATE_UNAVAILABLE),
    ],
)
async def test_entity_availability(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    human_status: AlarmAreaState,
    armed: int,
    alarm_state: AlarmControlPanelState,
) -> None:
    """Test all entities."""

    await setup_integration(hass, mock_vedo_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == AlarmControlPanelState.DISARMED

    vedo_query = AlarmDataObject(
        alarm_areas={
            0: ComelitVedoAreaObject(
                index=0,
                name="Area0",
                p1=True,
                p2=True,
                ready=False,
                armed=armed,
                alarm=False,
                alarm_memory=False,
                sabotage=False,
                anomaly=False,
                in_time=False,
                out_time=False,
                human_status=human_status,
            )
        },
        alarm_zones={
            0: ComelitVedoZoneObject(
                index=0,
                name="Zone0",
                status_api="0x000",
                status=0,
                human_status=AlarmZoneState.REST,
            )
        },
    )

    mock_vedo.get_all_areas_and_zones.return_value = vedo_query

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == alarm_state


@pytest.mark.parametrize(
    ("service", "alarm_state"),
    [
        (SERVICE_ALARM_DISARM, AlarmControlPanelState.DISARMED),
        (SERVICE_ALARM_ARM_AWAY, AlarmControlPanelState.ARMED_AWAY),
        (SERVICE_ALARM_ARM_HOME, AlarmControlPanelState.ARMED_HOME),
        (SERVICE_ALARM_ARM_NIGHT, AlarmControlPanelState.ARMED_NIGHT),
    ],
)
async def test_arming_disarming(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
    service: str,
    alarm_state: AlarmControlPanelState,
) -> None:
    """Test arming and disarming."""

    await setup_integration(hass, mock_vedo_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == AlarmControlPanelState.DISARMED

    await hass.services.async_call(
        ALARM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: VEDO_PIN},
        blocking=True,
    )

    mock_vedo.set_zone_status.assert_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == alarm_state


async def test_wrong_code(
    hass: HomeAssistant,
    mock_vedo: AsyncMock,
    mock_vedo_config_entry: MockConfigEntry,
) -> None:
    """Test disarm service with wrong code."""

    await setup_integration(hass, mock_vedo_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == AlarmControlPanelState.DISARMED

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: 1111},
        blocking=True,
    )

    mock_vedo.set_zone_status.assert_not_called()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == AlarmControlPanelState.DISARMED
