"""Tests for the TechnoVE switch platform."""
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion
from technove import TechnoVEConnectionError, TechnoVEError

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    ("entity_id", "method", "called_with_on", "called_with_off"),
    [
        (
            "switch.technove_station_auto_charge",
            "set_auto_charge",
            {"enabled": True},
            {"enabled": False},
        ),
    ],
)
async def test_switch_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
    called_with_on: dict[str, bool | int],
    called_with_off: dict[str, bool | int],
) -> None:
    """Test the creation and values of the TechnoVE switches."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


@pytest.mark.parametrize(
    ("entity_id", "method", "called_with_on", "called_with_off"),
    [
        (
            "switch.technove_station_auto_charge",
            "set_auto_charge",
            {"enabled": True},
            {"enabled": False},
        ),
    ],
)
async def test_switch_on_off(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
    called_with_on: dict[str, bool | int],
    called_with_off: dict[str, bool | int],
) -> None:
    """Test on/off services."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    assert method_mock.call_count == 1
    method_mock.assert_called_with(**called_with_on)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    assert method_mock.call_count == 2
    method_mock.assert_called_with(**called_with_off)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        (
            "switch.technove_station_auto_charge",
            "set_auto_charge",
        ),
    ],
)
async def test_invalid_response(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test invalid response, not becoming unavailable."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    method_mock.side_effect = TechnoVEError
    with pytest.raises(HomeAssistantError, match="Invalid response from TechnoVE API"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert method_mock.call_count == 1
    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        (
            "switch.technove_station_auto_charge",
            "set_auto_charge",
        ),
    ],
)
async def test_connection_error(
    hass: HomeAssistant,
    mock_technove: MagicMock,
    entity_id: str,
    method: str,
) -> None:
    """Test connection error, leading to becoming unavailable."""
    state = hass.states.get(entity_id)
    method_mock = getattr(mock_technove, method)

    method_mock.side_effect = TechnoVEConnectionError
    with pytest.raises(
        HomeAssistantError, match="Error communicating with TechnoVE API"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert method_mock.call_count == 1
    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE
