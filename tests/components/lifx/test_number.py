"""Tests for the LIFX number platform."""

from lifx import LifxError
import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import create_mock_infrared_light, create_mock_light

ENTITY_ID = "number.my_group_my_bulb_infrared_brightness"


@pytest.mark.parametrize(
    ("value", "level"),
    [
        pytest.param(0, 0.0, id="off"),
        pytest.param(25, 0.25, id="quarter"),
        pytest.param(60, 0.6, id="between-the-old-options"),
        pytest.param(100, 1.0, id="full"),
    ],
)
async def test_infrared_brightness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    value: int,
    level: float,
) -> None:
    """Test any level the device accepts can be set and read back."""
    device = create_mock_infrared_light()
    await async_setup_lifx_entry(hass, device)

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == f"{SERIAL}_infrared_brightness"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: value},
        blocking=True,
    )
    device.set_infrared.assert_awaited_once_with(level)

    device.state.infrared = level
    await async_trigger_update(hass)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == str(value)


async def test_light_without_infrared_has_no_number(hass: HomeAssistant) -> None:
    """Test a light with no infrared LEDs gets no infrared entity."""
    await async_setup_lifx_entry(hass, create_mock_light())

    assert hass.states.get(ENTITY_ID) is None


async def test_library_error_becomes_home_assistant_error(hass: HomeAssistant) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    device = create_mock_infrared_light()
    await async_setup_lifx_entry(hass, device)
    device.set_infrared.side_effect = LifxError("device unreachable")

    with pytest.raises(HomeAssistantError, match="device unreachable"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_VALUE: 50},
            blocking=True,
        )
