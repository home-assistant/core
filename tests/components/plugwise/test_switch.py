"""Tests for the Plugwise switch integration."""

from homeassistant.config_entries import ENTRY_STATE_LOADED

from tests.components.plugwise.common import async_init_integration


async def test_adam_climate_switch_entities(hass, mock_smile_adam):
    """Test creation of climate related switch entities."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_LOADED

    state = hass.states.get("switch.cv_pomp")
    assert str(state.state) == "on"

    state = hass.states.get("switch.fibaro_hc2")
    assert str(state.state) == "on"


async def test_adam_climate_switch_changes(hass, mock_smile_adam):
    """Test changing of climate related switch entities."""
    entry = await async_init_integration(hass, mock_smile_adam)
    assert entry.state == ENTRY_STATE_LOADED

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.cv_pomp"},
        blocking=True,
    )
    state = hass.states.get("switch.cv_pomp")
    assert str(state.state) == "off"

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.fibaro_hc2"},
        blocking=True,
    )
    state = hass.states.get("switch.fibaro_hc2")
    assert str(state.state) == "off"

    await hass.services.async_call(
        "switch",
        "toggle",
        {"entity_id": "switch.fibaro_hc2"},
        blocking=True,
    )
    state = hass.states.get("switch.fibaro_hc2")
    assert str(state.state) == "on"
