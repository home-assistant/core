"""Tests for the number platform."""

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.number.const import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FAKE_DUAL_HEAD_RGBWW_BULB,
    FAKE_MAC,
    async_push_update,
    async_setup_integration,
)


async def test_speed_operation(hass: HomeAssistant) -> None:
    """Test changing a speed."""
    bulb, _ = await async_setup_integration(hass, bulb_type=FAKE_DUAL_HEAD_RGBWW_BULB)
    await async_push_update(hass, bulb, {"mac": FAKE_MAC})
    entity_id = "number.mock_title_effect_speed"
    entity_registry = er.async_get(hass)
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


async def test_ratio_operation(hass: HomeAssistant) -> None:
    """Test changing a dual head ratio."""
    bulb, _ = await async_setup_integration(hass, bulb_type=FAKE_DUAL_HEAD_RGBWW_BULB)
    await async_push_update(hass, bulb, {"mac": FAKE_MAC})
    entity_id = "number.mock_title_dual_head_ratio"
    entity_registry = er.async_get(hass)
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
