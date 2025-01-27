"""The sensor tests for the tado platform."""

from unittest.mock import patch

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.common import load_fixture

child_lock_switch_entity = "switch.baseboard_heater_child_lock"


async def test_child_lock(hass: HomeAssistant) -> None:
    """Test creation of child lock entity."""

    await async_init_integration(hass)
    state = hass.states.get(child_lock_switch_entity)
    assert state.state == STATE_OFF


async def test_set_child_lock_on(hass: HomeAssistant) -> None:
    """Test enable child lock on switch."""

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_child_lock"
        ) as mock_set_state,
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.get_device_info",
            return_value=load_fixture("tado/device_wr4_child_lock_enabled.json"),
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: child_lock_switch_entity},
            blocking=True,
        )

    mock_set_state.assert_called_once()
    assert mock_set_state.call_args[0][1] is True


async def test_set_child_lock_off(hass: HomeAssistant) -> None:
    """Test disable child lock on switch."""

    await async_init_integration(hass)

    with (
        patch(
            "homeassistant.components.tado.PyTado.interface.api.Tado.set_child_lock"
        ) as mock_set_state,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: child_lock_switch_entity},
            blocking=True,
        )

    mock_set_state.assert_called_once()
    assert mock_set_state.call_args[0][1] is False
