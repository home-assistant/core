"""Tests for the Prosegur alarm control panel device."""

from unittest.mock import AsyncMock, patch

from pyprosegur.installation import Status
import pytest

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_component, entity_registry as er

from .conftest import CONTRACT

PROSEGUR_ALARM_ENTITY = f"alarm_control_panel.contract_{CONTRACT}"


@pytest.fixture
def mock_auth():
    """Setups authentication."""

    with patch("pyprosegur.auth.Auth.login", return_value=True):
        yield


@pytest.fixture(params=list(Status))
def mock_status(request):
    """Mock the status of the alarm."""

    install = AsyncMock()
    install.contract = CONTRACT
    install.status = request.param

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):
        yield


async def test_entity_registry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration,
    mock_auth,
    mock_status,
) -> None:
    """Tests that the devices are registered in the entity registry."""
    entry = entity_registry.async_get(PROSEGUR_ALARM_ENTITY)
    # Prosegur alarm device unique_id is the contract id associated to the alarm account
    assert entry.unique_id == CONTRACT

    await hass.async_block_till_done()

    state = hass.states.get(PROSEGUR_ALARM_ENTITY)

    assert state.attributes.get(ATTR_FRIENDLY_NAME) == f"Contract {CONTRACT}"
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 3


async def test_connection_error(
    hass: HomeAssistant, init_integration, mock_auth, mock_config_entry
) -> None:
    """Test the alarm control panel when connection can't be made to the cloud service."""

    install = AsyncMock()
    install.arm = AsyncMock(return_value=False)
    install.arm_partially = AsyncMock(return_value=True)
    install.disarm = AsyncMock(return_value=True)
    install.status = Status.ARMED

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):
        await hass.async_block_till_done()

    with patch(
        "pyprosegur.installation.Installation.retrieve", side_effect=ConnectionError
    ):
        await entity_component.async_update_entity(hass, PROSEGUR_ALARM_ENTITY)

        state = hass.states.get(PROSEGUR_ALARM_ENTITY)
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("code", "alarm_service", "alarm_state"),
    [
        (Status.ARMED, SERVICE_ALARM_ARM_AWAY, STATE_ALARM_ARMED_AWAY),
        (Status.PARTIALLY, SERVICE_ALARM_ARM_HOME, STATE_ALARM_ARMED_HOME),
        (Status.DISARMED, SERVICE_ALARM_DISARM, STATE_ALARM_DISARMED),
    ],
)
async def test_arm(
    hass: HomeAssistant, init_integration, mock_auth, code, alarm_service, alarm_state
) -> None:
    """Test the alarm control panel can be set to away."""

    install = AsyncMock()
    install.arm = AsyncMock(return_value=False)
    install.arm_partially = AsyncMock(return_value=True)
    install.disarm = AsyncMock(return_value=True)
    install.status = code

    with patch("pyprosegur.installation.Installation.retrieve", return_value=install):
        await hass.services.async_call(
            ALARM_DOMAIN,
            alarm_service,
            {ATTR_ENTITY_ID: PROSEGUR_ALARM_ENTITY},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(PROSEGUR_ALARM_ENTITY)
        assert state.state == alarm_state
