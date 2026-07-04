"""Tests for the KEBA charging station sensor platform."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_sensor_entities_created(hass: HomeAssistant) -> None:
    """Test that all expected sensor entities are created."""
    entity_ids = [
        "sensor.kc_p30_max_current",
        "sensor.kc_p30_energy_target",
        "sensor.kc_p30_charging_power",
        "sensor.kc_p30_session_energy",
        "sensor.kc_p30_total_energy",
    ]
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) is not None, f"{entity_id} not found"


@pytest.mark.usefixtures("init_integration")
async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensor states match snapshot."""
    entity_ids = [
        "sensor.kc_p30_max_current",
        "sensor.kc_p30_energy_target",
        "sensor.kc_p30_charging_power",
        "sensor.kc_p30_session_energy",
        "sensor.kc_p30_total_energy",
    ]
    for entity_id in entity_ids:
        assert hass.states.get(entity_id) == snapshot(name=entity_id)


@pytest.mark.usefixtures("init_integration")
async def test_charging_power_extra_attributes(hass: HomeAssistant) -> None:
    """Test that the charging power sensor exposes the expected extra attributes."""
    state = hass.states.get("sensor.kc_p30_charging_power")
    assert state is not None
    attrs = state.attributes
    assert "power_factor" in attrs
    assert "voltage_u1" in attrs
    assert "voltage_u2" in attrs
    assert "voltage_u3" in attrs
    assert "current_i1" in attrs
    assert "current_i2" in attrs
    assert "current_i3" in attrs


@pytest.mark.usefixtures("init_integration")
async def test_max_current_extra_attributes(hass: HomeAssistant) -> None:
    """Test that the max current sensor exposes the hardware limit attribute."""
    state = hass.states.get("sensor.kc_p30_max_current")
    assert state is not None
    assert "max_current_hardware" in state.attributes
