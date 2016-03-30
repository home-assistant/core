import pytest
import voluptuous as vol

import homeassistant.helpers.config_validation as cv


def test_latitude():
    """Test latitude validation."""
    schema = vol.Schema(cv.latitude)

    for value in ('invalid', None, -91, 91, '-91', '91', '123.01A'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ('-89', 89, '12.34'):
        schema(value)


def test_longitude():
    """Test longitude validation."""
    schema = vol.Schema(cv.longitude)

    for value in ('invalid', None, -181, 181, '-181', '181', '123.01A'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ('-179', 179, '12.34'):
        schema(value)


def test_icon():
    """Test icon validation."""
    schema = vol.Schema(cv.icon)

    for value in (False, 'work', 'icon:work'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema('mdi:work')


def test_platform_config():
    """Test platform config validation."""
    for value in (
        {'platform': 1},
        {},
        {'hello': 'world'},
    ):
        with pytest.raises(vol.MultipleInvalid):
            cv.PLATFORM_SCHEMA(value)

    for value in (
        {'platform': 'mqtt'},
        {'platform': 'mqtt', 'beer': 'yes'},
    ):
        cv.PLATFORM_SCHEMA(value)


def test_entity_id():
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_id)

    with pytest.raises(vol.MultipleInvalid):
        schema('invalid_entity')

    schema('sensor.light')


def test_entity_ids():
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_ids)

    for value in (
        'invalid_entity',
        'sensor.light,sensor_invalid',
        ['invalid_entity'],
        ['sensor.light', 'sensor_invalid'],
        ['sensor.light,sensor_invalid'],
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        [],
        ['sensor.light'],
        'sensor.light'
    ):
        schema(value)

    assert schema('sensor.light, light.kitchen ') == [
        'sensor.light', 'light.kitchen'
    ]


def test_temperature_unit():
    """Test temperature unit validation."""
    schema = vol.Schema(cv.temperature_unit)

    with pytest.raises(vol.MultipleInvalid):
        schema('K')

    schema('C')
    schema('F')


def test_time_zone():
    """Test time zone validation."""
    schema = vol.Schema(cv.time_zone)

    with pytest.raises(vol.MultipleInvalid):
        schema('America/Do_Not_Exist')

    schema('America/Los_Angeles')
    schema('UTC')
