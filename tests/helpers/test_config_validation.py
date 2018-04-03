"""Test config validators."""
from datetime import timedelta, datetime, date
import enum
import os
from socket import _GLOBAL_DEFAULT_TIMEOUT
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol

import homeassistant.helpers.config_validation as cv


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

    fake_file = 'this-file-does-not.exist'
    assert not os.path.isfile(fake_file)

    for value in ('invalid', None, -1, 0, 80000, fake_file):
        with pytest.raises(vol.Invalid):
            schema(value)

    # patching methods that allow us to fake a file existing
    # with write access
    with patch('os.path.isfile', Mock(return_value=True)), \
            patch('os.access', Mock(return_value=True)):
        schema('test.txt')


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
    options = (
        {},
        {'hello': 'world'},
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.PLATFORM_SCHEMA(value)

    options = (
        {'platform': 'mqtt'},
        {'platform': 'mqtt', 'beer': 'yes'},
    )
    for value in options:
        cv.PLATFORM_SCHEMA(value)


def test_ensure_list():
    """Test ensure_list."""
    schema = vol.Schema(cv.ensure_list)
    assert [] == schema(None)
    assert [1] == schema(1)
    assert [1] == schema([1])
    assert ['1'] == schema('1')
    assert ['1'] == schema(['1'])
    assert [{'1': '2'}] == schema({'1': '2'})


def test_entity_id():
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_id)

    with pytest.raises(vol.MultipleInvalid):
        schema('invalid_entity')

    assert schema('sensor.LIGHT') == 'sensor.light'


def test_entity_ids():
    """Test entity ID validation."""
    schema = vol.Schema(cv.entity_ids)

    options = (
        'invalid_entity',
        'sensor.light,sensor_invalid',
        ['invalid_entity'],
        ['sensor.light', 'sensor_invalid'],
        ['sensor.light,sensor_invalid'],
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        [],
        ['sensor.light'],
        'sensor.light'
    )
    for value in options:
        schema(value)

    assert schema('sensor.LIGHT, light.kitchen ') == [
        'sensor.light', 'light.kitchen'
    ]


def test_entity_domain():
    """Test entity domain validation."""
    schema = vol.Schema(cv.entity_domain('sensor'))

    options = (
        'invalid_entity',
        'cover.demo',
    )

    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            print(value)
            schema(value)

    assert schema('sensor.LIGHT') == 'sensor.light'


def test_entities_domain():
    """Test entities domain validation."""
    schema = vol.Schema(cv.entities_domain('sensor'))

    options = (
        None,
        '',
        'invalid_entity',
        ['sensor.light', 'cover.demo'],
        ['sensor.light', 'sensor_invalid'],
    )

    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        'sensor.light',
        ['SENSOR.light'],
        ['sensor.light', 'sensor.demo']
    )
    for value in options:
        schema(value)

    assert schema('sensor.LIGHT, sensor.demo ') == [
        'sensor.light', 'sensor.demo'
    ]
    assert schema(['sensor.light', 'SENSOR.demo']) == [
        'sensor.light', 'sensor.demo'
    ]


def test_ensure_list_csv():
    """Test ensure_list_csv."""
    schema = vol.Schema(cv.ensure_list_csv)

    options = (
        None,
        12,
        [],
        ['string'],
        'string1,string2'
    )
    for value in options:
        schema(value)

    assert schema('string1, string2 ') == [
        'string1', 'string2'
    ]


def test_event_schema():
    """Test event_schema validation."""
    options = (
        {}, None,
        {
            'event_data': {},
        },
        {
            'event': 'state_changed',
            'event_data': 1,
        },
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.EVENT_SCHEMA(value)

    options = (
        {'event': 'state_changed'},
        {'event': 'state_changed', 'event_data': {'hello': 'world'}},
    )
    for value in options:
        cv.EVENT_SCHEMA(value)


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

    options = (
        None, '', 'hello:world', '12:', '12:34:56:78',
        {}, {'wrong_key': -10}
    )
    for value in options:

        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        '8:20', '23:59', '-8:20', '-23:59:59', '-48:00', {'minutes': 5}, 1, '5'
    )
    for value in options:
        schema(value)

    assert timedelta(seconds=180) == schema('180')
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
    options = (
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
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            cv.SERVICE_SCHEMA(value)

    options = (
        {'service': 'homeassistant.turn_on'},
        {
            'service': 'homeassistant.turn_on',
            'entity_id': 'light.kitchen',
        },
        {
            'service': 'homeassistant.turn_on',
            'entity_id': ['light.kitchen', 'light.ceiling'],
        },
    )
    for value in options:
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


def test_x10_address():
    """Test x10 addr validator."""
    schema = vol.Schema(cv.x10_address)
    with pytest.raises(vol.Invalid):
        schema('Q1')
        schema('q55')
        schema('garbage_addr')

    schema('a1')
    schema('C11')


def test_template():
    """Test template validator."""
    schema = vol.Schema(cv.template)

    for value in (None, '{{ partial_print }', '{% if True %}Hello', ['test']):
        with pytest.raises(vol.Invalid,
                           message='{} not considered invalid'.format(value)):
            schema(value)

    options = (
        1, 'Hello',
        '{{ beer }}',
        '{% if 1 == 1 %}Hello{% else %}World{% endif %}',
    )
    for value in options:
        schema(value)


def test_template_complex():
    """Test template_complex validator."""
    schema = vol.Schema(cv.template_complex)

    for value in (None, '{{ partial_print }', '{% if True %}Hello'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        1, 'Hello',
        '{{ beer }}',
        '{% if 1 == 1 %}Hello{% else %}World{% endif %}',
        {'test': 1, 'test2': '{{ beer }}'},
        ['{{ beer }}', 1]
    )
    for value in options:
        schema(value)


def test_time_zone():
    """Test time zone validation."""
    schema = vol.Schema(cv.time_zone)

    with pytest.raises(vol.MultipleInvalid):
        schema('America/Do_Not_Exist')

    schema('America/Los_Angeles')
    schema('UTC')


def test_date():
    """Test date validation."""
    schema = vol.Schema(cv.date)

    for value in ['Not a date', '23:42', '2016-11-23T18:59:08']:
        with pytest.raises(vol.Invalid):
            schema(value)

    schema(datetime.now().date())
    schema('2016-11-23')


def test_time():
    """Test date validation."""
    schema = vol.Schema(cv.time)

    for value in ['Not a time', '2016-11-23', '2016-11-23T18:59:08']:
        with pytest.raises(vol.Invalid):
            schema(value)

    schema(datetime.now().time())
    schema('23:42:00')
    schema('23:42')


def test_datetime():
    """Test date time validation."""
    schema = vol.Schema(cv.datetime)
    for value in [date.today(), 'Wrong DateTime', '2016-11-23']:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema(datetime.now())
    schema('2016-11-23T18:59:08')


def test_deprecated(caplog):
    """Test deprecation log."""
    schema = vol.Schema({
        'venus': cv.boolean,
        'mars': cv.boolean
    })
    deprecated_schema = vol.All(
        cv.deprecated('mars'),
        schema
    )

    deprecated_schema({'venus': True})
    # pylint: disable=len-as-condition
    assert len(caplog.records) == 0

    deprecated_schema({'mars': True})
    assert len(caplog.records) == 1
    assert caplog.records[0].name == __name__
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please remove it from your configuration.") in caplog.text


def test_key_dependency():
    """Test key_dependency validator."""
    schema = vol.Schema(cv.key_dependency('beer', 'soda'))

    options = (
        {'beer': None}
    )
    for value in options:
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    options = (
        {'beer': None, 'soda': None},
        {'soda': None}, {}
    )
    for value in options:
        schema(value)


def test_has_at_least_one_key():
    """Test has_at_least_one_key validator."""
    schema = vol.Schema(cv.has_at_least_one_key('beer', 'soda'))

    for value in (None, [], {}, {'wine': None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({'beer': None}, {'soda': None}):
        schema(value)


def test_has_at_least_one_key_value():
    """Test has_at_least_one_key_value validator."""
    schema = vol.Schema(cv.has_at_least_one_key_value(('drink', 'beer'),
                                                      ('drink', 'soda'),
                                                      ('food', 'maultaschen')))

    for value in (None, [], {}, {'wine': None}, {'drink': 'water'}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({'drink': 'beer'}, {'food': 'maultaschen'},
                  {'drink': 'soda', 'food': 'maultaschen'}):
        schema(value)


def test_enum():
    """Test enum validator."""
    class TestEnum(enum.Enum):
        """Test enum."""

        value1 = "Value 1"
        value2 = "Value 2"

    schema = vol.Schema(cv.enum(TestEnum))

    with pytest.raises(vol.Invalid):
        schema('value3')


def test_socket_timeout():  # pylint: disable=invalid-name
    """Test socket timeout validator."""
    schema = vol.Schema(cv.socket_timeout)

    with pytest.raises(vol.Invalid):
        schema(0.0)

    with pytest.raises(vol.Invalid):
        schema(-1)

    assert _GLOBAL_DEFAULT_TIMEOUT == schema(None)

    assert schema(1) == 1.0


def test_matches_regex():
    """Test matches_regex validator."""
    schema = vol.Schema(cv.matches_regex('.*uiae.*'))

    with pytest.raises(vol.Invalid):
        schema(1.0)

    with pytest.raises(vol.Invalid):
        schema("  nrtd   ")

    test_str = "This is a test including uiae."
    assert(schema(test_str) == test_str)


def test_is_regex():
    """Test the is_regex validator."""
    schema = vol.Schema(cv.is_regex)

    with pytest.raises(vol.Invalid):
        schema("(")

    with pytest.raises(vol.Invalid):
        schema({"a dict": "is not a regex"})

    valid_re = ".*"
    schema(valid_re)
