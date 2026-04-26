"""Tests for hardware-conditional Peblar entities."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.peblar.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "init_integration_with_socket", [Platform.BINARY_SENSOR], indirect=True
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration_with_socket")
async def test_lock_state_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lock state binary sensor is created when socket hardware present."""
    entity_id = "binary_sensor.peblar_ev_charger_socket_lock"
    assert hass.states.get(entity_id) is not None

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.domain == BINARY_SENSOR_DOMAIN

    # LockState=false in fixture → unlocked → STATE_OFF
    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    "init_integration", [Platform.BINARY_SENSOR], indirect=True
)
@pytest.mark.usefixtures("init_integration")
async def test_lock_state_absent_without_socket(
    hass: HomeAssistant,
) -> None:
    """Test lock state entity absent when HwHasSocket=false (default fixture)."""
    assert hass.states.get("binary_sensor.peblar_ev_charger_socket_lock") is None


@pytest.mark.parametrize(
    "init_integration_with_socket", [Platform.BUTTON], indirect=True
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration_with_socket")
async def test_socket_unlock_button(
    hass: HomeAssistant,
    mock_peblar_with_socket: MagicMock,
) -> None:
    """Test socket unlock button is created and works when socket hardware present."""
    entity_id = "button.peblar_ev_charger_unlock_socket"
    assert hass.states.get(entity_id) is not None

    mocked_method = mock_peblar_with_socket.socket_unlock
    mocked_method.reset_mock()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_with()


@pytest.mark.parametrize(
    "init_integration_with_socket", [Platform.SWITCH], indirect=True
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration_with_socket")
async def test_socket_lock_switch(
    hass: HomeAssistant,
    mock_peblar_with_socket: MagicMock,
) -> None:
    """Test socket lock switch is created and works when socket hardware present."""
    entity_id = "switch.peblar_ev_charger_keep_socket_locked"
    assert hass.states.get(entity_id) is not None

    # UserKeepSocketLocked=false in fixture
    assert hass.states.get(entity_id).state == STATE_OFF

    mocked_method = mock_peblar_with_socket.socket_lock
    mocked_method.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_with(locked=True)

    mocked_method.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_with(locked=False)


@pytest.mark.parametrize(
    "init_integration", [Platform.SWITCH], indirect=True
)
@pytest.mark.usefixtures("init_integration")
async def test_socket_lock_absent_without_socket(
    hass: HomeAssistant,
) -> None:
    """Test socket lock entity absent when HwHasSocket=false (default fixture)."""
    assert hass.states.get("switch.peblar_ev_charger_keep_socket_locked") is None
