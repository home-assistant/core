"""Tests for the KEBA charging station binary sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_entities_created(hass: HomeAssistant) -> None:
    """Test that all expected binary sensor entities are created."""
    entity_ids = [
        "binary_sensor.kc_p30_status",
        "binary_sensor.kc_p30_plug",
        "binary_sensor.kc_p30_charging_state",
        "binary_sensor.kc_p30_failsafe_mode",
    ]
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) is not None, f"{entity_id} not found"


@pytest.mark.usefixtures("init_integration")
async def test_binary_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all binary sensor states match snapshot."""
    entity_ids = [
        "binary_sensor.kc_p30_status",
        "binary_sensor.kc_p30_plug",
        "binary_sensor.kc_p30_charging_state",
        "binary_sensor.kc_p30_failsafe_mode",
    ]
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) == snapshot(name=entity_id)


@pytest.mark.usefixtures("init_integration")
async def test_plug_extra_attributes(hass: HomeAssistant) -> None:
    """Test that the plug binary sensor exposes the expected extra attributes."""
    state = hass.states.get("binary_sensor.kc_p30_plug")
    assert state is not None
    attrs = state.attributes
    assert "plugged_on_wallbox" in attrs
    assert "plug_locked" in attrs
    assert "plugged_on_EV" in attrs


@pytest.mark.usefixtures("init_integration")
async def test_charging_state_extra_attributes(hass: HomeAssistant) -> None:
    """Test that the charging state binary sensor exposes the expected extra attributes."""
    state = hass.states.get("binary_sensor.kc_p30_charging_state")
    assert state is not None
    attrs = state.attributes
    assert "status" in attrs
    assert "max_charging_rate" in attrs


@pytest.mark.usefixtures("init_integration")
async def test_failsafe_extra_attributes(hass: HomeAssistant) -> None:
    """Test that the failsafe binary sensor exposes the expected extra attributes."""
    state = hass.states.get("binary_sensor.kc_p30_failsafe_mode")
    assert state is not None
    attrs = state.attributes
    assert "failsafe_timeout" in attrs
    assert "fallback_current" in attrs
