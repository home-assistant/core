"""Tests for the pvpc_hourly_pricing integration."""
from homeassistant.components.pvpc_hourly_pricing import ATTR_TARIFF
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT

FIXTURE_XML_DATA_2019_10_26 = "80-pvpcdesglosehorario-2019-10-26T23_59_59+00_00.xml"
FIXTURE_XML_DATA_2019_10_27 = "80-pvpcdesglosehorario-2019-10-27T23_59_59+00_00.xml"
FIXTURE_XML_DATA_2019_10_29 = "80-pvpcdesglosehorario-2019-10-29T23_59_59+00_00.xml"
FIXTURE_XML_DATA_2019_03_30 = "80-pvpcdesglosehorario-2019-03-30T23_59_59+00_00.xml"
FIXTURE_XML_DATA_2019_03_31 = "80-pvpcdesglosehorario-2019-03-31T23_59_59+00_00.xml"


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
