"""Tests for the number platform."""

from pywizlight import PilotParser

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.wiz.number import NUMBERS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FAKE_DUAL_HEAD_RGBWW_BULB,
    FAKE_MAC,
    FAKE_TURNABLE_BULB,
    _mocked_wizlight,
    async_push_update,
    async_setup_integration,
)


def test_ratio_support_without_state() -> None:
    """Test ratio support detection without an available device state."""
    bulb = _mocked_wizlight(None, None, FAKE_TURNABLE_BULB)
    bulb.state = None
    ratio_description = next(
        (
            description
            for description in NUMBERS
            if description.key == "dual_head_ratio"
        ),
        None,
    )

    assert ratio_description is not None
    assert ratio_description.supported_fn is not None
    assert not ratio_description.supported_fn(bulb)


async def test_speed_operation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test changing a speed."""
    bulb, _ = await async_setup_integration(hass, bulb_type=FAKE_DUAL_HEAD_RGBWW_BULB)
    await async_push_update(hass, bulb, {"mac": FAKE_MAC})
    entity_id = "number.mock_title_effect_speed"
    assert entity_registry.async_get(entity_id).unique_id == f"{FAKE_MAC}_effect_speed"
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await async_push_update(hass, bulb, {"mac": FAKE_MAC, "speed": 50})
    assert hass.states.get(entity_id).state == "50.0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 30},
        blocking=True,
    )
    bulb.set_speed.assert_called_with(30)
    await async_push_update(hass, bulb, {"mac": FAKE_MAC, "speed": 30})
    assert hass.states.get(entity_id).state == "30.0"


async def test_ratio_operation(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test changing a dual head ratio."""
    bulb, _ = await async_setup_integration(hass, bulb_type=FAKE_DUAL_HEAD_RGBWW_BULB)
    await async_push_update(hass, bulb, {"mac": FAKE_MAC})
    entity_id = "number.mock_title_dual_head_ratio"
    assert (
        entity_registry.async_get(entity_id).unique_id == f"{FAKE_MAC}_dual_head_ratio"
    )
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await async_push_update(hass, bulb, {"mac": FAKE_MAC, "ratio": 50})
    assert hass.states.get(entity_id).state == "50.0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 30},
        blocking=True,
    )
    bulb.set_ratio.assert_called_with(30)
    await async_push_update(hass, bulb, {"mac": FAKE_MAC, "ratio": 30})
    assert hass.states.get(entity_id).state == "30.0"


async def test_ratio_operation_without_dual_head_feature(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test changing a ratio reported by a light with an unadvertised dual head feature."""
    bulb = _mocked_wizlight(None, None, FAKE_TURNABLE_BULB)
    bulb.state = None

    async def _update_state() -> PilotParser:
        bulb.state = PilotParser({"mac": FAKE_MAC, "ratio": 50})
        return bulb.state

    bulb.updateState.side_effect = _update_state

    await async_setup_integration(hass, wizlight=bulb)

    bulb.updateState.assert_called_once()
    entity_id = "number.mock_title_dual_head_ratio"
    assert (
        entity_registry.async_get(entity_id).unique_id == f"{FAKE_MAC}_dual_head_ratio"
    )
    assert hass.states.get(entity_id).state == "50.0"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 30},
        blocking=True,
    )
    bulb.set_ratio.assert_called_with(30)
