"""Tests for the Telldus Live light platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.components.tellduslive.const import DIM
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

LIGHT = "light.kitchen"


@pytest.fixture
def dim_level() -> int | None:
    """Return the dim level reported by the device."""
    return 128


@pytest.fixture
def device(mock_tellduslive: MagicMock, dim_level: int | None) -> MagicMock:
    """Return a mocked device that is a dimmer."""
    device = mock_tellduslive.devices[0]
    device.methods = DIM
    device.is_on = True
    device.dim_level = dim_level
    return device


@pytest.mark.usefixtures("setup_integration")
async def test_light_state(hass: HomeAssistant) -> None:
    """Test the light state and brightness follow the device."""
    state = hass.states.get(LIGHT)

    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128


@pytest.mark.parametrize(
    ("service_data", "level"),
    [
        pytest.param({ATTR_BRIGHTNESS: 50}, 50, id="explicit"),
        pytest.param({}, 128, id="last_brightness"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_light_turn_on(
    hass: HomeAssistant, device: MagicMock, service_data: dict[str, int], level: int
) -> None:
    """Test turning on dims to the requested or last known brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LIGHT, **service_data},
        blocking=True,
    )

    device.dim.assert_called_once_with(level=level)


@pytest.mark.parametrize("dim_level", [0, None])
@pytest.mark.usefixtures("setup_integration")
async def test_light_turn_on_without_usable_brightness(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Test turning on falls back to full brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: LIGHT}, blocking=True
    )

    device.dim.assert_called_once_with(level=255)


@pytest.mark.usefixtures("setup_integration")
async def test_light_turn_off(hass: HomeAssistant, device: MagicMock) -> None:
    """Test turning the light off sends the command."""
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT}, blocking=True
    )

    device.turn_off.assert_called_once_with()


@pytest.mark.usefixtures("setup_integration")
async def test_light_command_rejected(hass: HomeAssistant, device: MagicMock) -> None:
    """Test a rejected command raises."""
    device.turn_off.return_value = False

    with pytest.raises(HomeAssistantError, match="did not accept the command"):
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: LIGHT}, blocking=True
        )
