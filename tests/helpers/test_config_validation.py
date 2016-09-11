"""Test config validators."""
from collections import OrderedDict
from datetime import timedelta
import os
import tempfile

import pytest
import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from tests.common import get_test_home_assistant


def test_boolean():
    """Test boolean validation."""
    schema = vol.Schema(cv.boolean)

    for value in ('T', 'negative', 'lock'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ('true', 'On', '1', 'YES', 'enable', 1, True):
        assert schema(value)

    for value in ('false', 'Off', '0', 'NO', 'disable', 0, False):
        assert not schema(value)


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


def test_port():
    """Test TCP/UDP network port."""
    schema = vol.Schema(cv.port)

    for value in ('invalid', None, -1, 0, 80000, '81000'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ('1000', 21, 24574):
        schema(value)


def test_isfile():
    """Validate that the value is an existing file."""
    schema = vol.Schema(cv.isfile)

    with tempfile.NamedTemporaryFile() as fp:
        pass

    for value in ('invalid', None, -1, 0, 80000, fp.name):
        with pytest.raises(vol.Invalid):
            schema(value)

    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_file = os.path.join(tmp_path, "test.txt")
        with open(tmp_file, "w") as tmp_handl:
            tmp_handl.write("test file")
        schema(tmp_file)


def test_url():
    """Test URL."""
    schema = vol.Schema(cv.url)

    for value in ('invalid', None, 100, 'htp://ha.io', 'http//ha.io',
                  'http://??,**', 'https://??,**'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ('http://localhost', 'https://localhost/test/index.html',
                  'http://home-assistant.io', 'http://home-assistant.io/test/',
                  'https://community.home-assistant.io/'):
        assert schema(value)


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

    assert 'sensor.light' == schema('sensor.LIGHT')


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

    assert schema('sensor.LIGHT, light.kitchen ') == [
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


def test_platform_validator():
    """Test platform validation."""
    # Prepares loading
    get_test_home_assistant()

    schema = vol.Schema(cv.platform_validator('light'))

    with pytest.raises(vol.MultipleInvalid):
        schema('platform_that_does_not_exist')

    schema('hue')


def test_icon():
    """Test icon validation."""
    schema = vol.Schema(cv.icon)

    for value in (False, 'work', 'icon:work'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema('mdi:work')


def test_time_period():
    """Test time_period validation."""
    schema = vol.Schema(cv.time_period)

    for value in (
        None, '', 1234, 'hello:world', '12:', '12:34:56:78',
        {}, {'wrong_key': -10}
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        '8:20', '23:59', '-8:20', '-23:59:59', '-48:00', {'minutes': 5}
    ):
        schema(value)

    assert timedelta(hours=23, minutes=59) == schema('23:59')
    assert -1 * timedelta(hours=1, minutes=15) == schema('-1:15')


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
        {
            'service': 'homeassistant.turn_on',
            'entity_id': 'light.kitchen',
        },
        {
            'service': 'homeassistant.turn_on',
            'entity_id': ['light.kitchen', 'light.ceiling'],
        },
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

    for value in (None, '{{ partial_print }', '{% if True %}Hello', ['test']):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        1, 'Hello',
        '{{ beer }}',
        '{% if 1 == 1 %}Hello{% else %}World{% endif %}',
    ):
        schema(value)


def test_template_complex():
    """Test template_complex validator."""
    schema = vol.Schema(cv.template_complex)

    for value in (None, '{{ partial_print }', '{% if True %}Hello'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        1, 'Hello',
        '{{ beer }}',
        '{% if 1 == 1 %}Hello{% else %}World{% endif %}',
        {'test': 1, 'test': '{{ beer }}'},
        ['{{ beer }}', 1]
    ):
        schema(value)


def test_time_zone():
    """Test time zone validation."""
    schema = vol.Schema(cv.time_zone)

    with pytest.raises(vol.MultipleInvalid):
        schema('America/Do_Not_Exist')

    schema('America/Los_Angeles')
    schema('UTC')


def test_key_dependency():
    """Test key_dependency validator."""
    schema = vol.Schema(cv.key_dependency('beer', 'soda'))

    for value in (
        {'beer': None}
    ):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in (
        {'beer': None, 'soda': None},
        {'soda': None}, {}
    ):
        schema(value)


def test_has_at_least_one_key():
    """Test has_at_least_one_key validator."""
    schema = vol.Schema(cv.has_at_least_one_key('beer', 'soda'))

    for value in (None, [], {}, {'wine': None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({'beer': None}, {'soda': None}):
        schema(value)


def test_ordered_dict_order():
    """Test ordered_dict validator."""
    schema = vol.Schema(cv.ordered_dict(int, cv.string))

    val = OrderedDict()
    val['first'] = 1
    val['second'] = 2

    validated = schema(val)

    assert isinstance(validated, OrderedDict)
    assert ['first', 'second'] == list(validated.keys())


def test_ordered_dict_key_validator():
    """Test ordered_dict key validator."""
    schema = vol.Schema(cv.ordered_dict(cv.match_all, cv.string))

    with pytest.raises(vol.Invalid):
        schema({None: 1})

    schema({'hello': 'world'})

    schema = vol.Schema(cv.ordered_dict(cv.match_all, int))

    with pytest.raises(vol.Invalid):
        schema({'hello': 1})

    schema({1: 'works'})


def test_ordered_dict_value_validator():
    """Test ordered_dict validator."""
    schema = vol.Schema(cv.ordered_dict(cv.string))

    with pytest.raises(vol.Invalid):
        schema({'hello': None})

    schema({'hello': 'world'})

    schema = vol.Schema(cv.ordered_dict(int))

    with pytest.raises(vol.Invalid):
        schema({'hello': 'world'})

    schema({'hello': 5})
