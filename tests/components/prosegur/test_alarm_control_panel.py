"""Tests for the Prosegur alarm control panel device."""

from pyprosegur.installation import Status
from pytest import fixture, mark

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
)
from homeassistant.helpers import entity_component

from .common import CONTRACT, setup_platform

PROSEGUR_ALARM_ENTITY = f"alarm_control_panel.contract_{CONTRACT}"


@fixture(params=[s.value for s in Status])
def mock_auth(request, aioclient_mock):
    """Setups authentication and initial info."""
    aioclient_mock.post(
        "https://smart.prosegur.com/smart-server/ws/access/login",
        json={"data": {"token": "123456789"}},
    )
    aioclient_mock.get(
        "https://smart.prosegur.com/smart-server/ws/installation",
        json={
            "data": [{"installationId": "1234abcd", "status": request.param}],
            "result": {"code": 200},
        },
    )


async def test_entity_registry(hass):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, ALARM_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get(PROSEGUR_ALARM_ENTITY)
    # Prosegur alarm device unique_id is the contract id associated to the alarm account
    assert entry.unique_id == CONTRACT


async def test_attributes(hass, aioclient_mock, mock_auth):
    """Test the alarm control panel attributes are correct."""
    await setup_platform(hass, ALARM_DOMAIN)

    await hass.async_block_till_done()

    state = hass.states.get(PROSEGUR_ALARM_ENTITY)

    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "contract 1234abcd"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 3


@mark.parametrize(
    "code, alarm_service, alarm_state",
    [
        ("AT", SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        ("AP", SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        ("DA", SERVICE_ALARM_DISARM, STATE_ALARM_DISARMED),
    ],
)
async def test_arm(hass, aioclient_mock, mock_auth, code, alarm_service, alarm_state):
    """Test the alarm control panel can be set to away."""

    await setup_platform(hass, ALARM_DOMAIN)

    aioclient_mock.put(
        "https://smart.prosegur.com/smart-server/ws/installation/1234abcd/status",
    )
    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: PROSEGUR_ALARM_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "https://smart.prosegur.com/smart-server/ws/installation",
        json={
            "data": [{"installationId": "1234abcd", "status": code}],
            "result": {"code": 200},
        },
    )
    await entity_component.async_update_entity(hass, PROSEGUR_ALARM_ENTITY)
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    state = hass.states.get(PROSEGUR_ALARM_ENTITY)
    assert state.state == alarm_state
