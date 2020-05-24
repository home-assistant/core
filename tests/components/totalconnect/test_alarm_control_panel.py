"""Tests for the TotalConnect alarm control panel device."""
from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)

from .common import (
    RESPONSE_ARM_FAILURE,
    RESPONSE_ARM_SUCCESS,
    RESPONSE_ARMED_AWAY,
    RESPONSE_ARMED_STAY,
    RESPONSE_DISARM_FAILURE,
    RESPONSE_DISARM_SUCCESS,
    RESPONSE_DISARMED,
    setup_platform,
)

from tests.async_mock import patch
from tests.components.alarm_control_panel import common

ENTITY_ID = "alarm_control_panel.test"
CODE = "-1"


async def test_attributes(hass):
    """Test the alarm control panel attributes are correct."""
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        return_value=RESPONSE_DISARMED,
    ) as mock_request:
        await setup_platform(hass, ALARM_DOMAIN)
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_ALARM_DISARMED
        mock_request.assert_called_once()
        assert state.attributes.get(ATTR_FRIENDLY_NAME) == "test"


async def test_arm_home_success(hass):
    """Test arm home method success."""
    RESPONSES = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_STAY]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=RESPONSES,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        await common.async_alarm_arm_home(hass)
        await hass.async_block_till_done()
        assert STATE_ALARM_ARMED_HOME == hass.states.get(ENTITY_ID).state


async def test_arm_home_failure(hass):
    """Test arm home method failure."""
    RESPONSES = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_DISARMED]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=RESPONSES,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        await common.async_alarm_arm_home(hass)
        await hass.async_block_till_done()
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state


async def test_arm_away_success(hass):
    """Test arm away method success."""
    RESPONSES = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_AWAY]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=RESPONSES,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        await common.async_alarm_arm_away(hass)
        await hass.async_block_till_done()
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state


async def test_arm_away_failure(hass):
    """Test arm away method failure."""
    RESPONSES = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_DISARMED]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=RESPONSES,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        await common.async_alarm_arm_away(hass)
        await hass.async_block_till_done()
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state


async def test_disarm_success(hass):
    """Test disarm method success."""
    RESPONSES = [RESPONSE_ARMED_AWAY, RESPONSE_DISARM_SUCCESS, RESPONSE_DISARMED]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=RESPONSES,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state

        await common.async_alarm_disarm(hass)
        await hass.async_block_till_done()
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state


async def test_disarm_failure(hass):
    """Test disarm method failure."""
    RESPONSES = [RESPONSE_ARMED_AWAY, RESPONSE_DISARM_FAILURE, RESPONSE_ARMED_AWAY]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=RESPONSES,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state

        await common.async_alarm_disarm(hass)
        await hass.async_block_till_done()
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state
