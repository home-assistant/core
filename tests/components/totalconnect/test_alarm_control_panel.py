"""Tests for the TotalConnect alarm control panel device."""
from unittest.mock import patch

import pytest

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
from homeassistant.exceptions import HomeAssistantError

from .common import (
    RESPONSE_ARM_FAILURE,
    RESPONSE_ARM_SUCCESS,
    RESPONSE_ARMED_AWAY,
    RESPONSE_ARMED_STAY,
    RESPONSE_DISARM_FAILURE,
    RESPONSE_DISARM_SUCCESS,
    RESPONSE_DISARMED,
    RESPONSE_USER_CODE_INVALID,
    setup_platform,
)

ENTITY_ID = "alarm_control_panel.test"
CODE = "-1"
DATA = {ATTR_ENTITY_ID: ENTITY_ID}


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
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_STAY]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_ARM_HOME, DATA, blocking=True
        )

        await hass.async_block_till_done()
        assert STATE_ALARM_ARMED_HOME == hass.states.get(ENTITY_ID).state


async def test_arm_home_failure(hass):
    """Test arm home method failure."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_DISARMED]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_HOME, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm home test."
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state


async def test_arm_home_invalid_usercode(hass):
    """Test arm home method with invalid usercode."""
    responses = [RESPONSE_DISARMED, RESPONSE_USER_CODE_INVALID, RESPONSE_DISARMED]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_HOME, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm home test."
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state


async def test_arm_away_success(hass):
    """Test arm away method success."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_SUCCESS, RESPONSE_ARMED_AWAY]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_ARM_AWAY, DATA, blocking=True
        )
        await hass.async_block_till_done()
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state


async def test_arm_away_failure(hass):
    """Test arm away method failure."""
    responses = [RESPONSE_DISARMED, RESPONSE_ARM_FAILURE, RESPONSE_DISARMED]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_ARM_AWAY, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to arm away test."
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state


async def test_disarm_success(hass):
    """Test disarm method success."""
    responses = [RESPONSE_ARMED_AWAY, RESPONSE_DISARM_SUCCESS, RESPONSE_DISARMED]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state

        await hass.services.async_call(
            ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA, blocking=True
        )
        await hass.async_block_till_done()
        assert STATE_ALARM_DISARMED == hass.states.get(ENTITY_ID).state


async def test_disarm_failure(hass):
    """Test disarm method failure."""
    responses = [RESPONSE_ARMED_AWAY, RESPONSE_DISARM_FAILURE, RESPONSE_ARMED_AWAY]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to disarm test."
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state


async def test_disarm_invalid_usercode(hass):
    """Test disarm method failure."""
    responses = [RESPONSE_ARMED_AWAY, RESPONSE_USER_CODE_INVALID, RESPONSE_ARMED_AWAY]
    with patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ):
        await setup_platform(hass, ALARM_DOMAIN)
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state

        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(
                ALARM_DOMAIN, SERVICE_ALARM_DISARM, DATA, blocking=True
            )
            await hass.async_block_till_done()
        assert f"{err.value}" == "TotalConnect failed to disarm test."
        assert STATE_ALARM_ARMED_AWAY == hass.states.get(ENTITY_ID).state
