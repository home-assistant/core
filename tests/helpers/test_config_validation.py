"""Test config validators."""
from datetime import date, datetime, timedelta
import enum
import os
from socket import _GLOBAL_DEFAULT_TIMEOUT
from unittest.mock import Mock, patch
import uuid

import pytest
import voluptuous as vol

import homeassistant
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


def test_ip_address():
    """Test IP address validation."""
    test = vol.Schema(cv.ip_address)
    invalid = (
        None, True, False, 123, 123.456, 123+456j,
        [], [1, 2, 3, 4], ['a', 'b', 'c', 'd'],
        {}, {'a': 1, 'b': 2, 'c': 3, 'd': 4},
        '', 'abc', '123', '!@#$%', 'abc::123::def', '...', ':::::::',
        '1.2.3', '1.2.3.4.5', 'abc1.2.3.4', '1.2.3.4abc', '.2.3.4', '1..3.4',
        '1.2.3.', '*.2.3.4', '1.*.3.4', '1.2.*.4', '1.2.3.*', 'a.2.3.4',
        '1.b.3.4', '1.2.c.4', '1.2.3.d', '256.2.3.4', '1.256.3.4', '1.2.256.4',
        '1.2.3.256', '1:2:3:4', '1-2-3-4', '1/2/3/4', '1_2_3_4', '1,2,3,4',
        '1 2 3 4', '1:2:3:4:5:6:7', '1:2:3:4:5:6:7:8:9', 'xyz1:2:3:4:5:6:7:8',
        '1:2:3:4:5:6:7:8xyz', ':2:3:4:5:6:7:8', '1:2:3:4:5:6:7:',
        '*:2:3:4:5:6:7:8', '1:2:3:*:5:6:7:8', '1:2:3:4:5:6:7:*',
        'g:2:3:4:5:6:7:8', '1:2:3:g:5:6:7:8', '1:2:3:4:5:6:7:g',
        '10000:2:3:4:5:6:7:8', '1:2:3:10000:5:6:7:8', '1:2:3:4:5:6:7:10000',
        '1.2.3.4.5.6.7.8', '1-2-3-4-5-6-7-8', '1/2/3/4/5/6/7/8',
        '1_2_3_4_5_6_7_8', '1,2,3,4,5,6,7,8', '1 2 3 4 5 6 7 8')
    valid = (
        '172.16.54.1', '192.168.0.1', '10.0.0.1', '255.255.255.1',
        '2001:db8:85a3:0:0:8a2e:370:7334', 'FE80::B3FF:FE1E:8329')
    for value in invalid:
        with pytest.raises(vol.MultipleInvalid):
            test(value)
    for value in valid:
        assert test(value)


def test_ipv4_address():
    """Test IP address validation."""
    test = vol.Schema(cv.ipv4_address)
    invalid = (
        None, True, False, 123, 123.456, 123+456j,
        [], [1, 2, 3, 4], ['a', 'b', 'c', 'd'],
        {}, {'a': 1, 'b': 2, 'c': 3, 'd': 4},
        '', 'abc', '123', '!@#$%', '...',
        '1.2.3', '1.2.3.4.5', 'abc1.2.3.4', '1.2.3.4abc', '.2.3.4', '1..3.4',
        '1.2.3.', '*.2.3.4', '1.*.3.4', '1.2.*.4', '1.2.3.*', 'a.2.3.4',
        '1.b.3.4', '1.2.c.4', '1.2.3.d', '256.2.3.4', '1.256.3.4', '1.2.256.4',
        '1.2.3.256', '1:2:3:4', '1-2-3-4', '1/2/3/4', '1_2_3_4', '1,2,3,4',
        '1 2 3 4', '2001:db8:85a3:0:0:8a2e:370:7334', 'FE80::B3FF:FE1E:8329')
    valid = ('172.16.54.1', '192.168.0.1', '10.0.0.1', '255.255.255.1')
    for value in invalid:
        with pytest.raises(vol.MultipleInvalid):
            test(value)
    for value in valid:
        assert test(value)


def test_ipv6_address():
    """Test IP address validation."""
    test = vol.Schema(cv.ipv6_address)
    invalid = (
        None, True, False, 123, 123.456, 123+456j,
        [], [1, 2, 3, 4], ['a', 'b', 'c', 'd'],
        {}, {'a': 1, 'b': 2, 'c': 3, 'd': 4},
        '', 'abc', '123', '!@#$%', ':::::::', 'abc::123::def',
        '1:2:3:4:5:6:7', '1:2:3:4:5:6:7:8:9', 'xyz1:2:3:4:5:6:7:8',
        '1:2:3:4:5:6:7:8xyz', ':2:3:4:5:6:7:8', '1:2:3:4:5:6:7:',
        '*:2:3:4:5:6:7:8', '1:2:3:*:5:6:7:8', '1:2:3:4:5:6:7:*',
        'g:2:3:4:5:6:7:8', '1:2:3:g:5:6:7:8', '1:2:3:4:5:6:7:g',
        '10000:2:3:4:5:6:7:8', '1:2:3:10000:5:6:7:8', '1:2:3:4:5:6:7:10000',
        '1.2.3.4.5.6.7.8', '1-2-3-4-5-6-7-8', '1/2/3/4/5/6/7/8',
        '1_2_3_4_5_6_7_8', '1,2,3,4,5,6,7,8', '1 2 3 4 5 6 7 8',
        '172.16.54.1', '192.168.0.1', '10.0.0.1', '255.255.255.1')
    valid = ('2001:db8:85a3:0:0:8a2e:370:7334', 'FE80::B3FF:FE1E:8329')
    for value in invalid:
        with pytest.raises(vol.MultipleInvalid):
            test(value)
    for value in valid:
        assert test(value)


def test_mac48_address():
    """Test 48-bit MAC address validation."""
    test = vol.Schema(cv.mac48_address)
    invalid = (
        None, True, False, 123, 123.456, 123+456j,
        [], [1, 2, 3, 4], ['a', 'b', 'c', 'd'],
        {}, {'a': 1, 'b': 2, 'c': 3, 'd': 4},
        '', 'abc', '123', '!@#$%', ':::::', '-----', '..', '--',
        'a1-b2-c3-d4-e5', 'a1-b2-c3-d4-e5-f6-a7', 'xyza1-b2-c3-d4-e5-f6',
        'a1-b2-c3-d4-e5-f6xyz', '-b2-c3-d4-e5-f6', 'a1-b2--d4-e5-f6',
        'a1-b2-c3-d4-e5-', '*-b2-c3-d4-e5-f6', 'a1-b2-*-d4-e5-f6',
        'a1-b2-c3-d4-e5-*', 'g1-b2-c3-d4-e5-f6', 'a1-b2-g3-d4-e5-f6',
        'a1-b2-c3-d4-e5-g6', '100-b2-c3-d4-e5-f6', 'a1-b2-100-d4-e5-f6',
        'a1-b2-c3-d4-e5-100', 'a1.b2.c3.d4.e5.f6', 'a1,b2,c3,d4,e5,f6',
        'a1/b2/c3/d4/e5/f6', 'a1_b2_c3_d4_e5_f6', 'a1b2:c3d4:e5f6',
        'a1b2,c3d4,e5f6', 'a1b2/c3d4/e5f6', 'a1b2_c3d4_e5f6',
        'a1-b2:c3-d4:e5-f6')
    valid = (
        'a1-b2-c3-d4-e4-f6', 'A1-B2-C3-D4-E5-F6', 'a1:b2:c3:d4:e4:f6',
        'A1:B2:C3:D4:E5:F6', 'a1b2.c3d4.e5f6', 'A1B2.C3D4.E5F6',
        'a1b2-c3d4-e5f6', 'A1B2-C3D4-E5F6', 'a1b2c3d4e4f6', 'A1B2C3D4E5F6',
        'a1 b2 c3 d4 e4 f6', 'A1 B2 C3 D4 E5 F6', 'a1b2 c3d4 e4f6',
        'A1B2 C3D4 E5F6', 'a-1-b-2-c-3', 'A-1-B-2-C-3', 'A:1:B:2:C:3',
        'a:1:b:2:c:3', 'a 1 b 2 c 3', 'A 1 B 2 C 3')
    for value in invalid:
        with pytest.raises(vol.MultipleInvalid):
            test(value)
    for value in valid:
        assert test(value)


def test_mac64_address():
    """Test 64-bit MAC address validation."""
    test = vol.Schema(cv.mac64_address)
    invalid = (
        None, True, False, 123, 123.456, 123+456j,
        [], [1, 2, 3, 4], ['a', 'b', 'c', 'd'],
        {}, {'a': 1, 'b': 2, 'c': 3, 'd': 4},
        '', 'abc', '123', '!@#$%', ':::::::', '-------', '...', '---',
        'a1-b2-c3-d4-e5-f6-a7', 'a1-b2-c3-d4-e5-f6-a7-b8-c9',
        'xyza1-b2-c3-d4-e5-f6-a7-b8', 'a1-b2-c3-d4-e5-f6-a7-b8xyz',
        '-b2-c3-d4-e5-f6-a7-b8', 'a1-b2-c3--e5-f6-a7-b8',
        'a1-b2-c3-d4-e5-f6-a7-', '*-b2-c3-d4-e5-f6-a7-b8',
        'a1-b2-*-d4-e5-f6-a7-b8', 'a1-b2-c3-d4-e5-f6-a7-*',
        'g1-b2-c3-d4-e5-f6-a7-b8', 'a1-b2-g3-d4-e5-f6-a7-b8',
        'a1-b2-c3-d4-e5-f6-a7-g8', '100-b2-c3-d4-e5-f6-a7-b8',
        'a1-b2-100-d4-e5-f6-a7-b8', 'a1-b2-c3-d4-e5-f6-a7-100',
        'a1.b2.c3.d4.e5.f6.a7.b8', 'a1,b2,c3,d4,e5,f6,a7,b8',
        'a1/b2/c3/d4/e5/f6/a7/b8', 'a1_b2_c3_d4_e5_f6_a7_b8',
        'a1b2:c3d4:e5f6:a7b8', 'a1b2,c3d4,e5f6,a7b8', 'a1b2/c3d4/e5f6/a7b8',
        'a1b2_c3d4_e5f6_a7b8', 'a1-b2:c3-d4:e5-f6:a7-b8')
    valid = (
        'a1-b2-c3-d4-e4-f6-a7-b8', 'A1-B2-C3-D4-E5-F6-A7-B8',
        'a1:b2:c3:d4:e5:f6:a7:b8', 'A1:B2:C3:D4:E5:F6:A7:B8',
        'a1b2.c3d4.e5f6.a7b8', 'A1B2.C3D4.E5F6.A7B8', 'a1b2-c3d4-e5f6-a7b8',
        'A1B2-C3D4-E5F6-A7B8', 'a1b2c3d4e4f6a7b8', 'A1B2C3D4E5F6A7B8',
        'a1 b2 c3 d4 e4 f6 a7 b8', 'A1 B2 C3 D4 E5 F6 A7 B8',
        'a1b2 c3d4 e4f6 a7b8', 'A1B2 C3D4 E5F6 A7B8', 'a-1-b-2-c-3-d-4',
        'A-1-B-2-C-3-D-4', 'a:1:b:2:c:3:d:4', 'A:1:B:2:C:3:D:4',
        'a 1 b 2 c 3 d 4', 'A 1 B 2 C 3 D 4')
    for value in invalid:
        with pytest.raises(vol.MultipleInvalid):
            test(value)
    for value in valid:
        assert test(value)


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
        cv.PLATFORM_SCHEMA_BASE(value)


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

    for value in (False, 'work'):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    schema('mdi:work')
    schema('custom:prefix')


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


def test_remove_falsy():
    """Test remove falsy."""
    assert cv.remove_falsy([0, None, 1, "1", {}, [], ""]) == [1, "1"]


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
            'service': 'light.turn_on',
            'entity_id': 'all',
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

    with pytest.raises(vol.Invalid):
        schema(None)

    with pytest.raises(vol.Invalid):
        schema([])

    with pytest.raises(vol.Invalid):
        schema({})

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
        with pytest.raises(vol.Invalid):
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

    # ensure the validator didn't mutate the input
    assert options == (
        1, 'Hello',
        '{{ beer }}',
        '{% if 1 == 1 %}Hello{% else %}World{% endif %}',
        {'test': 1, 'test2': '{{ beer }}'},
        ['{{ beer }}', 1]
    )


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


@pytest.fixture
def schema():
    """Create a schema used for testing deprecation."""
    return vol.Schema({
        'venus': cv.boolean,
        'mars': cv.boolean,
        'jupiter': cv.boolean
    })


@pytest.fixture
def version(monkeypatch):
    """Patch the version used for testing to 0.5.0."""
    monkeypatch.setattr(homeassistant.const, '__version__', '0.5.0')


def test_deprecated_with_no_optionals(caplog, schema):
    """
    Test deprecation behaves correctly when optional params are None.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema without changing any values
        - No warning or difference in output if key is not provided
    """
    deprecated_schema = vol.All(
        cv.deprecated('mars'),
        schema
    )

    test_data = {'mars': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert caplog.records[0].name == __name__
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please remove it from your configuration") in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {'venus': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_replacement_key(caplog, schema):
    """
    Test deprecation behaves correctly when only a replacement key is provided.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning or difference in output if neither key nor
            replacement_key are provided
    """
    deprecated_schema = vol.All(
        cv.deprecated('mars', replacement_key='jupiter'),
        schema
    )

    test_data = {'mars': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please replace it with 'jupiter'") in caplog.text
    assert {'jupiter': True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {'jupiter': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {'venus': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_invalidation_version(caplog, schema, version):
    """
    Test deprecation behaves correctly with only an invalidation_version.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema without changing any values
        - No warning or difference in output if key is not provided
        - Once the invalidation_version is crossed, raises vol.Invalid if key
            is detected
    """
    deprecated_schema = vol.All(
        cv.deprecated('mars', invalidation_version='1.0.0'),
        schema
    )

    message = ("The 'mars' option (with value 'True') is deprecated, "
               "please remove it from your configuration. "
               "This option will become invalid in version 1.0.0")

    test_data = {'mars': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert message in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {'venus': False}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    invalidated_schema = vol.All(
        cv.deprecated('mars', invalidation_version='0.1.0'),
        schema
    )
    test_data = {'mars': True}
    with pytest.raises(vol.MultipleInvalid) as exc_info:
        invalidated_schema(test_data)
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please remove it from your configuration. This option will "
            "become invalid in version 0.1.0") == str(exc_info.value)


def test_deprecated_with_replacement_key_and_invalidation_version(
        caplog, schema, version
):
    """
    Test deprecation behaves with a replacement key & invalidation_version.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning or difference in output if neither key nor
            replacement_key are provided
        - Once the invalidation_version is crossed, raises vol.Invalid if key
        is detected
    """
    deprecated_schema = vol.All(
        cv.deprecated(
            'mars', replacement_key='jupiter', invalidation_version='1.0.0'
        ),
        schema
    )

    warning = ("The 'mars' option (with value 'True') is deprecated, "
               "please replace it with 'jupiter'. This option will become "
               "invalid in version 1.0.0")

    test_data = {'mars': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert warning in caplog.text
    assert {'jupiter': True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {'jupiter': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {'venus': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    invalidated_schema = vol.All(
        cv.deprecated(
            'mars', replacement_key='jupiter', invalidation_version='0.1.0'
        ),
        schema
    )
    test_data = {'mars': True}
    with pytest.raises(vol.MultipleInvalid) as exc_info:
        invalidated_schema(test_data)
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please replace it with 'jupiter'. This option will become "
            "invalid in version 0.1.0") == str(exc_info.value)


def test_deprecated_with_default(caplog, schema):
    """
    Test deprecation behaves correctly with a default value.

    This is likely a scenario that would never occur.

    Expected behavior:
        - Behaves identically as when the default value was not present
    """
    deprecated_schema = vol.All(
        cv.deprecated('mars', default=False),
        schema
    )

    test_data = {'mars': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert caplog.records[0].name == __name__
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please remove it from your configuration") in caplog.text
    assert test_data == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {'venus': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output


def test_deprecated_with_replacement_key_and_default(caplog, schema):
    """
    Test deprecation with a replacement key and default.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning if neither key nor replacement_key are provided
            - Adds replacement_key with default value in this case
    """
    deprecated_schema = vol.All(
        cv.deprecated('mars', replacement_key='jupiter', default=False),
        schema
    )

    test_data = {'mars': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please replace it with 'jupiter'") in caplog.text
    assert {'jupiter': True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {'jupiter': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {'venus': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert {'venus': True, 'jupiter': False} == output

    deprecated_schema_with_default = vol.All(
        vol.Schema({
            'venus': cv.boolean,
            vol.Optional('mars', default=False): cv.boolean,
            vol.Optional('jupiter', default=False): cv.boolean
        }),
        cv.deprecated('mars', replacement_key='jupiter', default=False)
    )

    test_data = {'mars': True}
    output = deprecated_schema_with_default(test_data.copy())
    assert len(caplog.records) == 1
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please replace it with 'jupiter'") in caplog.text
    assert {'jupiter': True} == output


def test_deprecated_with_replacement_key_invalidation_version_default(
        caplog, schema, version
):
    """
    Test deprecation with a replacement key, invalidation_version & default.

    Expected behavior:
        - Outputs the appropriate deprecation warning if key is detected
        - Processes schema moving the value from key to replacement_key
        - Processes schema changing nothing if only replacement_key provided
        - No warning if only replacement_key provided
        - No warning if neither key nor replacement_key are provided
            - Adds replacement_key with default value in this case
        - Once the invalidation_version is crossed, raises vol.Invalid if key
        is detected
    """
    deprecated_schema = vol.All(
        cv.deprecated(
            'mars', replacement_key='jupiter', invalidation_version='1.0.0',
            default=False
        ),
        schema
    )

    test_data = {'mars': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 1
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please replace it with 'jupiter'. This option will become "
            "invalid in version 1.0.0") in caplog.text
    assert {'jupiter': True} == output

    caplog.clear()
    assert len(caplog.records) == 0

    test_data = {'jupiter': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert test_data == output

    test_data = {'venus': True}
    output = deprecated_schema(test_data.copy())
    assert len(caplog.records) == 0
    assert {'venus': True, 'jupiter': False} == output

    invalidated_schema = vol.All(
        cv.deprecated(
            'mars', replacement_key='jupiter', invalidation_version='0.1.0'
        ),
        schema
    )
    test_data = {'mars': True}
    with pytest.raises(vol.MultipleInvalid) as exc_info:
        invalidated_schema(test_data)
    assert ("The 'mars' option (with value 'True') is deprecated, "
            "please replace it with 'jupiter'. This option will become "
            "invalid in version 0.1.0") == str(exc_info.value)


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


def test_has_at_most_one_key():
    """Test has_at_most_one_key validator."""
    schema = vol.Schema(cv.has_at_most_one_key('beer', 'soda'))

    for value in (None, [], {'beer': None, 'soda': None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({}, {'beer': None}, {'soda': None}):
        schema(value)


def test_has_at_least_one_key():
    """Test has_at_least_one_key validator."""
    schema = vol.Schema(cv.has_at_least_one_key('beer', 'soda'))

    for value in (None, [], {}, {'wine': None}):
        with pytest.raises(vol.MultipleInvalid):
            schema(value)

    for value in ({'beer': None}, {'soda': None}):
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
    assert schema(test_str) == test_str


def test_is_regex():
    """Test the is_regex validator."""
    schema = vol.Schema(cv.is_regex)

    with pytest.raises(vol.Invalid):
        schema("(")

    with pytest.raises(vol.Invalid):
        schema({"a dict": "is not a regex"})

    valid_re = ".*"
    schema(valid_re)


def test_comp_entity_ids():
    """Test config validation for component entity IDs."""
    schema = vol.Schema(cv.comp_entity_ids)

    for valid in ('ALL', 'all', 'AlL', 'light.kitchen', ['light.kitchen'],
                  ['light.kitchen', 'light.ceiling'], []):
        schema(valid)

    for invalid in (['light.kitchen', 'not-entity-id'], '*', ''):
        with pytest.raises(vol.Invalid):
            schema(invalid)


def test_schema_with_slug_keys_allows_old_slugs(caplog):
    """Test schema with slug keys allowing old slugs."""
    schema = cv.schema_with_slug_keys(str)

    with patch.dict(cv.INVALID_SLUGS_FOUND, clear=True):
        for value in ('_world', 'wow__yeah'):
            caplog.clear()
            # Will raise if not allowing old slugs
            schema({value: 'yo'})
            assert "Found invalid slug {}".format(value) in caplog.text

        assert len(cv.INVALID_SLUGS_FOUND) == 2


def test_entity_id_allow_old_validation(caplog):
    """Test schema allowing old entity_ids."""
    schema = vol.Schema(cv.entity_id)

    with patch.dict(cv.INVALID_ENTITY_IDS_FOUND, clear=True):
        for value in ('hello.__world', 'great.wow__yeah'):
            caplog.clear()
            # Will raise if not allowing old entity ID
            schema(value)
            assert "Found invalid entity_id {}".format(value) in caplog.text

        assert len(cv.INVALID_ENTITY_IDS_FOUND) == 2


def test_uuid4_hex(caplog):
    """Test uuid validation."""
    schema = vol.Schema(cv.uuid4_hex)

    for value in ['Not a hex string', '0', 0]:
        with pytest.raises(vol.Invalid):
            schema(value)

    with pytest.raises(vol.Invalid):
        # the 13th char should be 4
        schema('a03d31b22eee1acc9b90eec40be6ed23')

    with pytest.raises(vol.Invalid):
        # the 17th char should be 8-a
        schema('a03d31b22eee4acc7b90eec40be6ed23')

    _hex = uuid.uuid4().hex
    assert schema(_hex) == _hex
    assert schema(_hex.upper()) == _hex
