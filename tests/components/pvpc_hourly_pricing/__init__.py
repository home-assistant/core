"""Tests for the pvpc_hourly_pricing integration."""
from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT


def check_valid_state(state, tariff: str, value=None, key_attr=None):
    """Ensure that sensor has a valid state and attributes."""
    assert state
    assert state.attributes[ATTR_TARIFF] == tariff
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€/kWh"
    # safety margins for current electricity price (it shouldn't be out of [0, 0.2])
    assert -0.1 < float(state.state) < 0.3

    if value is not None:
        assert abs(float(state.state) - value) < 1e-6
    if key_attr is not None:
        assert abs(float(state.state) - state.attributes[key_attr]) < 1e-6
