"""Tests for the pvpc_hourly_pricing integration."""
from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT

FIXTURE_JSON_DATA_2019_10_26 = "PVPC_CURV_DD_2019_10_26.json"
FIXTURE_JSON_DATA_2019_10_27 = "PVPC_CURV_DD_2019_10_27.json"
FIXTURE_JSON_DATA_2019_10_29 = "PVPC_CURV_DD_2019_10_29.json"
FIXTURE_JSON_DATA_2019_03_30 = "PVPC_CURV_DD_2019_03_30.json"
FIXTURE_JSON_DATA_2019_03_31 = "PVPC_CURV_DD_2019_03_31.json"


def check_valid_state(state, tariff: str, value=None, key_attr=None):
    """Ensure that sensor has a valid state and attributes."""
    assert state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "€/kWh"
    try:
        _ = float(state.state)
        # safety margins for current electricity price (it shouldn't be out of [0, 0.2])
        assert -0.1 < float(state.state) < 0.3
        assert state.attributes[ATTR_TARIFF] == tariff
    except ValueError:
        pass

    if value is not None and isinstance(value, str):
        assert state.state == value
    elif value is not None:
        assert abs(float(state.state) - value) < 1e-6
    if key_attr is not None:
        assert abs(float(state.state) - state.attributes[key_attr]) < 1e-6
