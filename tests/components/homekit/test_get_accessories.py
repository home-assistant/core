"""Package to test the get_accessory method."""
from unittest.mock import patch, MagicMock

from homeassistant.core import State
from homeassistant.components.homekit import (
    TYPES, get_accessory, import_types)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, ATTR_SUPPORTED_FEATURES,
    TEMP_CELSIUS, TEMP_FAHRENHEIT, STATE_UNKNOWN)


def test_import_types():
    """Test if all type files are imported correctly."""
    try:
        import_types()
        assert True
    # pylint: disable=broad-except
    except Exception:
        assert False


def test_component_not_supported():
    """Test with unsupported component."""
    state = State('demo.unsupported', STATE_UNKNOWN)

    assert True if get_accessory(None, state) is None else False


def test_sensor_temperature_celsius():
    """Test temperature sensor with Celsius as unit."""
    mock_type = MagicMock()
    with patch.dict(TYPES, {'TemperatureSensor': mock_type}):
        state = State('sensor.temperature', '23',
                      {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
        get_accessory(None, state)
    assert len(mock_type.mock_calls) == 1


# pylint: disable=invalid-name
def test_sensor_temperature_fahrenheit():
    """Test temperature sensor with Fahrenheit as unit."""
    mock_type = MagicMock()
    with patch.dict(TYPES, {'TemperatureSensor': mock_type}):
        state = State('sensor.temperature', '74',
                      {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
        get_accessory(None, state)
    assert len(mock_type.mock_calls) == 1


def test_cover_set_position():
    """Test cover with support for set_cover_position."""
    mock_type = MagicMock()
    with patch.dict(TYPES, {'Window': mock_type}):
        state = State('cover.set_position', 'open',
                      {ATTR_SUPPORTED_FEATURES: 4})
        get_accessory(None, state)
    assert len(mock_type.mock_calls) == 1
