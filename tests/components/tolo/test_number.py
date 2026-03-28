"""Tests for the TOLO Sauna number platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Entity IDs based on registration order: power_timer, salt_bath_timer, fan_timer
POWER_TIMER_ENTITY_ID = "number.tolo_sauna"
SALT_BATH_TIMER_ENTITY_ID = "number.tolo_sauna_2"
FAN_TIMER_ENTITY_ID = "number.tolo_sauna_3"


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "expected_value"),
    [
        (POWER_TIMER_ENTITY_ID, 30),
        (SALT_BATH_TIMER_ENTITY_ID, 25),
        (FAN_TIMER_ENTITY_ID, 20),
    ],
)
async def test_number_state(
    hass: HomeAssistant,
    entity_id: str,
    expected_value: int,
) -> None:
    """Test number entity states reflect settings values."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == expected_value


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "value", "setter_method", "expected_arg"),
    [
        (POWER_TIMER_ENTITY_ID, 15, "set_power_timer", 15),
        (SALT_BATH_TIMER_ENTITY_ID, 30, "set_salt_bath_timer", 30),
        (FAN_TIMER_ENTITY_ID, 10, "set_fan_timer", 10),
    ],
)
async def test_set_number_value(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
    entity_id: str,
    value: int,
    setter_method: str,
    expected_arg: int,
) -> None:
    """Test setting a number value."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    getattr(mock_tolo_client, setter_method).assert_called_once_with(expected_arg)


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "setter_method"),
    [
        (POWER_TIMER_ENTITY_ID, "set_power_timer"),
        (SALT_BATH_TIMER_ENTITY_ID, "set_salt_bath_timer"),
        (FAN_TIMER_ENTITY_ID, "set_fan_timer"),
    ],
)
async def test_set_number_value_zero_sends_none(
    hass: HomeAssistant,
    mock_tolo_client: MagicMock,
    entity_id: str,
    setter_method: str,
) -> None:
    """Test setting a number value to 0 sends None (disables timer)."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 0},
        blocking=True,
    )
    getattr(mock_tolo_client, setter_method).assert_called_once_with(None)
