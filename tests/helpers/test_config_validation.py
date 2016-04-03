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


def test_platform_config():
    """Test platform config validation."""
    for value in (
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


def test_event_schema():
    """Test event_schema validation."""
    for value in (
        {}, None,
        {
            'event_data': {},
        },
        {
            'event': 'state_changed',
            'event_data': 1,
        },
    ):
        with pytest.raises(vol.MultipleInvalid):
            cv.EVENT_SCHEMA(value)

    for value in (
        {'event': 'state_changed'},
        {'event': 'state_changed', 'event_data': {'hello': 'world'}},
    ):
        cv.EVENT_SCHEMA(value)


def test_icon():
    """Test icon validation."""
    schema = vol.Schema(cv.icon)

    for value in (False, 'work', 'icon:work'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema('mdi:work')


def test_service():
    """Test service validation."""
    schema = vol.Schema(cv.service)

    with pytest.raises(vol.MultipleInvalid):
        schema('invalid_turn_on')

    schema('homeassistant.turn_on')


def test_service_schema():
    """Test service_schema validation."""
    for value in (
        {}, None,
        {
            'service': 'homeassistant.turn_on',
            'service_template': 'homeassistant.turn_on'
        },
        {
            'data': {'entity_id': 'light.kitchen'},
        },
        {
            'service': 'homeassistant.turn_on',
            'data': None
        },
        {
            'service': 'homeassistant.turn_on',
            'data_template': {
                'brightness': '{{ no_end'
            }
        },
    ):
        with pytest.raises(vol.MultipleInvalid):
            cv.SERVICE_SCHEMA(value)

    for value in (
        {'service': 'homeassistant.turn_on'},
    ):
        cv.SERVICE_SCHEMA(value)


def test_slug():
    """Test slug validation."""
    schema = vol.Schema(cv.slug)

    for value in (None, 'hello world'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (12345, 'hello'):
        schema(value)


def test_string():
    """Test string validation."""
    schema = vol.Schema(cv.string)

    with pytest.raises(vol.MultipleInvalid):
        schema(None)

    for value in (True, 1, 'hello'):
        schema(value)


def test_temperature_unit():
    """Test temperature unit validation."""
    schema = vol.Schema(cv.temperature_unit)

    with pytest.raises(vol.MultipleInvalid):
        schema('K')

    schema('C')
    schema('F')


def test_template():
    """Test template validator."""
    schema = vol.Schema(cv.template)

    for value in (
        None, '{{ partial_print }', '{% if True %}Hello'
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        1, 'Hello',
        '{{ beer }}',
        '{% if 1 == 1 %}Hello{% else %}World{% endif %}',
    ):
        schema(value)


def test_time_zone():
    """Test time zone validation."""
    schema = vol.Schema(cv.time_zone)

    with pytest.raises(vol.MultipleInvalid):
        schema('America/Do_Not_Exist')

    schema('America/Los_Angeles')
    schema('UTC')


def test_dict_validator():
    """Test DictValidator."""
    schema = vol.Schema(cv.DictValidator(cv.entity_ids, cv.slug))

    for value in (
        None,
        {'invalid slug': 'sensor.temp'},
        {'hello world': 'invalid_entity'}
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        {},
        {'hello_world': 'sensor.temp'},
    ):
        schema(value)

    assert schema({'hello_world': 'sensor.temp'}) == \
        {'hello_world': ['sensor.temp']}


def test_has_at_least_one_key():
    """Test has_at_least_one_key validator."""
    schema = vol.Schema(cv.has_at_least_one_key(['beer', 'soda']))

    for value in (None, [], {}, {'wine': None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({'beer': None}, {'soda': None}):
        schema(value)
