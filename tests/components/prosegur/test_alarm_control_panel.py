"""Tests for the Prosegur alarm control panel device."""

from unittest.mock import AsyncMock, patch

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
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_component, entity_registry as er

from .common import CONTRACT, setup_platform

PROSEGUR_ALARM_ENTITY = f"alarm_control_panel.contract_{CONTRACT}"


@fixture
def mock_auth():
    """Setups authentication."""

    with patch("pyprosegur.auth.Auth.login", return_value=True):
        yield


@fixture(params=list(Status))
def mock_status(request):
    """Mock the status of the alarm."""

    install = AsyncMock()
    install.contract = "123"
    install.installationId = "1234abcd"
    install.status = request.param

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):
        yield


async def test_entity_registry(hass, mock_auth, mock_status):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get(PROSEGUR_ALARM_ENTITY)
    # Prosegur alarm device unique_id is the contract id associated to the alarm account
    assert entry.unique_id == CONTRACT

    await hass.async_block_till_done()

    state = hass.states.get(PROSEGUR_ALARM_ENTITY)

    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "contract 1234abcd"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 3


async def test_connection_error(hass, mock_auth):
    """Test the alarm control panel when connection can't be made to the cloud service."""

    install = AsyncMock()
    install.arm = AsyncMock(return_value=False)
    install.arm_partially = AsyncMock(return_value=True)
    install.disarm = AsyncMock(return_value=True)
    install.status = Status.ARMED

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):

        await setup_platform(hass)

        await hass.async_block_till_done()

    with patch(
        "pyprosegur.installation.Installation.retrieve", side_effect=ConnectionError
    ):

        await entity_component.async_update_entity(hass, PROSEGUR_ALARM_ENTITY)

        state = hass.states.get(PROSEGUR_ALARM_ENTITY)
        assert state.state == STATE_UNAVAILABLE


@mark.parametrize(
    "code, alarm_service, alarm_state",
    [
        (Status.ARMED, SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (Status.PARTIALLY, SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (Status.DISARMED, SERVICE_ALARM_DISARM, STATE_ALARM_DISARMED),
    ],
)
async def test_arm(hass, mock_auth, code, alarm_service, alarm_state):
    """Test the alarm control panel can be set to away."""

    install = AsyncMock()
    install.arm = AsyncMock(return_value=False)
    install.arm_partially = AsyncMock(return_value=True)
    install.disarm = AsyncMock(return_value=True)
    install.status = code

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):
        await setup_platform(hass)

        await hass.services.async_call(
            ALARM_DOMAIN,
            alarm_service,
            {ATTR_ENTITY_ID: PROSEGUR_ALARM_ENTITY},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(PROSEGUR_ALARM_ENTITY)
        assert state.state == alarm_state
