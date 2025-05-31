import pytest

from homeassistant.components.rexense.const import DEFAULT_PORT, DOMAIN, REXSENSE_SENSOR_TYPES


def test_default_port():
    assert isinstance(DEFAULT_PORT, int)
    assert DEFAULT_PORT == 80


def test_domain():
    assert isinstance(DOMAIN, str)


def test_sensor_types_structure():
    assert isinstance(REXSENSE_SENSOR_TYPES, dict)
    assert 'Voltage' in REXSENSE_SENSOR_TYPES
