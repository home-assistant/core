"""Tests for the LIFX number platform."""

from lifx import LifxError
import pytest

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberService,
    NumberServiceArgument,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import SERIAL, async_setup_lifx_entry, async_trigger_update
from .helpers import (
    INFRARED_NUMBER_ENTITY_ID,
    create_mock_infrared_light,
    create_mock_light,
)


@pytest.mark.parametrize(
    ("value", "level", "refreshed_level"),
    [
        pytest.param(0, 0.0, 0 / 65535, id="off"),
        pytest.param(25, 0.25, 16383 / 65535, id="quarter"),
        pytest.param(60, 0.6, 39321 / 65535, id="between-the-select-options"),
        pytest.param(100, 1.0, 65535 / 65535, id="full"),
    ],
)
async def test_infrared_brightness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    value: int,
    level: float,
    refreshed_level: float,
) -> None:
    """Test any percentage can be set and is read back from the firmware level."""
    device = create_mock_infrared_light()
    await async_setup_lifx_entry(hass, device)

    entity = entity_registry.async_get(INFRARED_NUMBER_ENTITY_ID)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == f"{SERIAL}_infrared_brightness"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        NumberService.SET_VALUE,
        {
            TargetKey.ENTITY_ID: INFRARED_NUMBER_ENTITY_ID,
            NumberServiceArgument.VALUE: value,
        },
        blocking=True,
    )
    device.set_infrared.assert_awaited_once_with(level)

    device.state.infrared = refreshed_level
    await async_trigger_update(hass)
    state = hass.states.get(INFRARED_NUMBER_ENTITY_ID)
    assert state
    assert float(state.state) == value


async def test_light_without_infrared_has_no_number(hass: HomeAssistant) -> None:
    """Test a light with no infrared LEDs gets no infrared entity."""
    await async_setup_lifx_entry(hass, create_mock_light())

    assert hass.states.get(INFRARED_NUMBER_ENTITY_ID) is None


async def test_library_error_becomes_home_assistant_error(hass: HomeAssistant) -> None:
    """Test a library failure surfaces as a Home Assistant error."""
    device = create_mock_infrared_light()
    await async_setup_lifx_entry(hass, device)
    device.set_infrared.side_effect = LifxError("device unreachable")

    with pytest.raises(HomeAssistantError, match="device unreachable"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            NumberService.SET_VALUE,
            {
                TargetKey.ENTITY_ID: INFRARED_NUMBER_ENTITY_ID,
                NumberServiceArgument.VALUE: 50,
            },
            blocking=True,
        )
