"""Test for smart home alexa support."""
import asyncio
import json
from uuid import uuid4

import pytest

from homeassistant.const import TEMP_FAHRENHEIT, CONF_UNIT_OF_MEASUREMENT
from homeassistant.setup import async_setup_component
from homeassistant.components import alexa
from homeassistant.components.alexa import smart_home
from homeassistant.helpers import entityfilter

from tests.common import async_mock_service

DEFAULT_CONFIG = smart_home.Config(should_expose=lambda entity_id: True)


def get_new_request(namespace, name, endpoint=None):
    """Generate a new API message."""
    raw_msg = {
        'directive': {
            'header': {
                'namespace': namespace,
                'name': name,
                'messageId': str(uuid4()),
                'correlationToken': str(uuid4()),
                'payloadVersion': '3',
            },
            'endpoint': {
                'scope': {
                    'type': 'BearerToken',
                    'token': str(uuid4()),
                },
                'endpointId': endpoint,
            },
            'payload': {},
        }
    }

    if not endpoint:
        raw_msg['directive'].pop('endpoint')

    return raw_msg


def test_create_api_message_defaults():
    """Create a API message response of a request with defaults."""
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#xy')
    request = request['directive']

    msg = smart_home.api_message(request, payload={'test': 3})

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['messageId'] is not None
    assert msg['header']['messageId'] != request['header']['messageId']
    assert msg['header']['correlationToken'] == \
        request['header']['correlationToken']
    assert msg['header']['name'] == 'Response'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['header']['payloadVersion'] == '3'

    assert 'test' in msg['payload']
    assert msg['payload']['test'] == 3

    assert msg['endpoint'] == request['endpoint']


def test_create_api_message_special():
    """Create a API message response of a request with non defaults."""
    request = get_new_request('Alexa.PowerController', 'TurnOn')
    request = request['directive']

    request['header'].pop('correlationToken')

    msg = smart_home.api_message(request, 'testName', 'testNameSpace')

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['messageId'] is not None
    assert msg['header']['messageId'] != request['header']['messageId']
    assert 'correlationToken' not in msg['header']
    assert msg['header']['name'] == 'testName'
    assert msg['header']['namespace'] == 'testNameSpace'
    assert msg['header']['payloadVersion'] == '3'

    assert msg['payload'] == {}
    assert 'endpoint' not in msg


@asyncio.coroutine
def test_wrong_version(hass):
    """Test with wrong version."""
    msg = get_new_request('Alexa.PowerController', 'TurnOn')
    msg['directive']['header']['payloadVersion'] = '2'

    with pytest.raises(AssertionError):
        yield from smart_home.async_handle_message(hass, DEFAULT_CONFIG, msg)


@asyncio.coroutine
def test_discovery_request(hass):
    """Test alexa discovery request."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # setup test devices
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})

    hass.states.async_set(
        'light.test_1', 'on', {'friendly_name': "Test light 1"})
    hass.states.async_set(
        'light.test_2', 'on', {
            'friendly_name': "Test light 2", 'supported_features': 1
        })
    hass.states.async_set(
        'light.test_3', 'on', {
            'friendly_name': "Test light 3", 'supported_features': 19
        })

    hass.states.async_set(
        'script.test', 'off', {'friendly_name': "Test script"})
    hass.states.async_set(
        'script.test_2', 'off', {'friendly_name': "Test script 2",
                                 'can_cancel': True})

    hass.states.async_set(
        'input_boolean.test', 'off', {'friendly_name': "Test input boolean"})

    hass.states.async_set(
        'scene.test', 'off', {'friendly_name': "Test scene"})

    hass.states.async_set(
        'fan.test_1', 'off', {'friendly_name': "Test fan 1"})

    hass.states.async_set(
        'fan.test_2', 'off', {
            'friendly_name': "Test fan 2", 'supported_features': 1,
            'speed_list': ['low', 'medium', 'high']
        })

    hass.states.async_set(
        'lock.test', 'off', {'friendly_name': "Test lock"})

    hass.states.async_set(
        'media_player.test', 'off', {
            'friendly_name': "Test media player",
            'supported_features': 20925,
            'volume_level': 1
        })

    hass.states.async_set(
        'alert.test', 'off', {'friendly_name': "Test alert"})

    hass.states.async_set(
        'automation.test', 'off', {'friendly_name': "Test automation"})

    hass.states.async_set(
        'group.test', 'off', {'friendly_name': "Test group"})

    hass.states.async_set(
        'cover.test', 'off', {
            'friendly_name': "Test cover", 'supported_features': 255,
            'position': 85
        })

    hass.states.async_set(
        'sensor.test_temp', '59', {
            'friendly_name': "Test Temp Sensor",
            'unit_of_measurement': TEMP_FAHRENHEIT,
        })

    # This sensor measures a quantity not applicable to Alexa, and should not
    # be discovered.
    hass.states.async_set(
        'sensor.test_sickness', '0.1', {
            'friendly_name': "Test Space Sickness Sensor",
            'unit_of_measurement': 'garn',
        })

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)

    assert 'event' in msg
    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 17
    assert msg['header']['name'] == 'Discover.Response'
    assert msg['header']['namespace'] == 'Alexa.Discovery'

    for appliance in msg['payload']['endpoints']:
        if appliance['endpointId'] == 'switch#test':
            assert appliance['displayCategories'][0] == "SWITCH"
            assert appliance['friendlyName'] == "Test switch"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.PowerController'
            continue

        if appliance['endpointId'] == 'light#test_1':
            assert appliance['displayCategories'][0] == "LIGHT"
            assert appliance['friendlyName'] == "Test light 1"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.PowerController'
            continue

        if appliance['endpointId'] == 'light#test_2':
            assert appliance['displayCategories'][0] == "LIGHT"
            assert appliance['friendlyName'] == "Test light 2"
            assert len(appliance['capabilities']) == 2

            caps = set()
            for feature in appliance['capabilities']:
                caps.add(feature['interface'])

            assert 'Alexa.BrightnessController' in caps
            assert 'Alexa.PowerController' in caps

            continue

        if appliance['endpointId'] == 'light#test_3':
            assert appliance['displayCategories'][0] == "LIGHT"
            assert appliance['friendlyName'] == "Test light 3"
            assert len(appliance['capabilities']) == 4

            caps = set()
            for feature in appliance['capabilities']:
                caps.add(feature['interface'])

            assert 'Alexa.BrightnessController' in caps
            assert 'Alexa.PowerController' in caps
            assert 'Alexa.ColorController' in caps
            assert 'Alexa.ColorTemperatureController' in caps

            continue

        if appliance['endpointId'] == 'script#test':
            assert appliance['displayCategories'][0] == "ACTIVITY_TRIGGER"
            assert appliance['friendlyName'] == "Test script"
            assert len(appliance['capabilities']) == 1
            capability = appliance['capabilities'][-1]
            assert capability['interface'] == 'Alexa.SceneController'
            assert not capability['supportsDeactivation']
            continue

        if appliance['endpointId'] == 'script#test_2':
            assert len(appliance['capabilities']) == 1
            capability = appliance['capabilities'][-1]
            assert capability['supportsDeactivation']
            continue

        if appliance['endpointId'] == 'input_boolean#test':
            assert appliance['displayCategories'][0] == "OTHER"
            assert appliance['friendlyName'] == "Test input boolean"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.PowerController'
            continue

        if appliance['endpointId'] == 'scene#test':
            assert appliance['displayCategories'][0] == "SCENE_TRIGGER"
            assert appliance['friendlyName'] == "Test scene"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.SceneController'
            continue

        if appliance['endpointId'] == 'fan#test_1':
            assert appliance['displayCategories'][0] == "OTHER"
            assert appliance['friendlyName'] == "Test fan 1"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.PowerController'
            continue

        if appliance['endpointId'] == 'fan#test_2':
            assert appliance['displayCategories'][0] == "OTHER"
            assert appliance['friendlyName'] == "Test fan 2"
            assert len(appliance['capabilities']) == 2

            caps = set()
            for feature in appliance['capabilities']:
                caps.add(feature['interface'])

            assert 'Alexa.PercentageController' in caps
            assert 'Alexa.PowerController' in caps
            continue

        if appliance['endpointId'] == 'lock#test':
            assert appliance['displayCategories'][0] == "SMARTLOCK"
            assert appliance['friendlyName'] == "Test lock"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.LockController'
            continue

        if appliance['endpointId'] == 'media_player#test':
            assert appliance['displayCategories'][0] == "TV"
            assert appliance['friendlyName'] == "Test media player"
            assert len(appliance['capabilities']) == 3
            caps = set()
            for feature in appliance['capabilities']:
                caps.add(feature['interface'])

            assert 'Alexa.PowerController' in caps
            assert 'Alexa.Speaker' in caps
            assert 'Alexa.PlaybackController' in caps
            continue

        if appliance['endpointId'] == 'alert#test':
            assert appliance['displayCategories'][0] == "OTHER"
            assert appliance['friendlyName'] == "Test alert"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.PowerController'
            continue

        if appliance['endpointId'] == 'automation#test':
            assert appliance['displayCategories'][0] == "OTHER"
            assert appliance['friendlyName'] == "Test automation"
            assert len(appliance['capabilities']) == 1
            assert appliance['capabilities'][-1]['interface'] == \
                'Alexa.PowerController'
            continue

        if appliance['endpointId'] == 'group#test':
            assert appliance['displayCategories'][0] == "SCENE_TRIGGER"
            assert appliance['friendlyName'] == "Test group"
            assert len(appliance['capabilities']) == 1
            capability = appliance['capabilities'][-1]
            assert capability['interface'] == 'Alexa.SceneController'
            assert capability['supportsDeactivation'] is True
            continue

        if appliance['endpointId'] == 'cover#test':
            assert appliance['displayCategories'][0] == "DOOR"
            assert appliance['friendlyName'] == "Test cover"
            assert len(appliance['capabilities']) == 2

            caps = set()
            for feature in appliance['capabilities']:
                caps.add(feature['interface'])

            assert 'Alexa.PercentageController' in caps
            assert 'Alexa.PowerController' in caps
            continue

        if appliance['endpointId'] == 'sensor#test_temp':
            assert appliance['displayCategories'][0] == 'TEMPERATURE_SENSOR'
            assert appliance['friendlyName'] == 'Test Temp Sensor'
            assert len(appliance['capabilities']) == 1
            capability = appliance['capabilities'][0]
            assert capability['interface'] == 'Alexa.TemperatureSensor'
            assert capability['retrievable'] is True
            properties = capability['properties']
            assert {'name': 'temperature'} in properties['supported']
            continue

        raise AssertionError("Unknown appliance!")


@asyncio.coroutine
def test_exclude_filters(hass):
    """Test exclusion filters."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # setup test devices
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})

    hass.states.async_set(
        'script.deny', 'off', {'friendly_name': "Blocked script"})

    hass.states.async_set(
        'cover.deny', 'off', {'friendly_name': "Blocked cover"})

    config = smart_home.Config(should_expose=entityfilter.generate_filter(
        include_domains=[],
        include_entities=[],
        exclude_domains=['script'],
        exclude_entities=['cover.deny'],
    ))

    msg = yield from smart_home.async_handle_message(hass, config, request)
    yield from hass.async_block_till_done()

    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 1


@asyncio.coroutine
def test_include_filters(hass):
    """Test inclusion filters."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # setup test devices
    hass.states.async_set(
        'switch.deny', 'on', {'friendly_name': "Blocked switch"})

    hass.states.async_set(
        'script.deny', 'off', {'friendly_name': "Blocked script"})

    hass.states.async_set(
        'automation.allow', 'off', {'friendly_name': "Allowed automation"})

    hass.states.async_set(
        'group.allow', 'off', {'friendly_name': "Allowed group"})

    config = smart_home.Config(should_expose=entityfilter.generate_filter(
        include_domains=['automation', 'group'],
        include_entities=['script.deny'],
        exclude_domains=[],
        exclude_entities=[],
    ))

    msg = yield from smart_home.async_handle_message(hass, config, request)
    yield from hass.async_block_till_done()

    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 3


@asyncio.coroutine
def test_api_entity_not_exists(hass):
    """Test api turn on process without entity."""
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#test')

    call_switch = async_mock_service(hass, 'switch', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_switch) == 0
    assert msg['header']['name'] == 'ErrorResponse'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['payload']['type'] == 'NO_SUCH_ENDPOINT'


@asyncio.coroutine
def test_api_function_not_implemented(hass):
    """Test api call that is not implemented to us."""
    request = get_new_request('Alexa.HAHAAH', 'Sweet')
    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['name'] == 'ErrorResponse'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['payload']['type'] == 'INTERNAL_ERROR'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['alert', 'automation', 'cover',
                                    'input_boolean', 'light',
                                    'switch'])
def test_api_turn_on(hass, domain):
    """Test api turn on process."""
    request = get_new_request(
        'Alexa.PowerController', 'TurnOn', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call_domain = domain

    if domain == 'cover':
        call = async_mock_service(hass, call_domain, 'open_cover')
    else:
        call = async_mock_service(hass, call_domain, 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['alert', 'automation', 'cover', 'group',
                                    'input_boolean', 'light', 'script',
                                    'switch'])
def test_api_turn_off(hass, domain):
    """Test api turn on process."""
    request = get_new_request(
        'Alexa.PowerController', 'TurnOff', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'on', {
            'friendly_name': "Test {}".format(domain)
        })

    call_domain = domain

    if domain == 'group':
        call_domain = 'homeassistant'

    if domain == 'cover':
        call = async_mock_service(hass, call_domain, 'close_cover')
    else:
        call = async_mock_service(hass, call_domain, 'turn_off')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
def test_api_set_brightness(hass):
    """Test api set brightness process."""
    request = get_new_request(
        'Alexa.BrightnessController', 'SetBrightness', 'light#test')

    # add payload
    request['directive']['payload']['brightness'] = '50'

    # setup test devices
    hass.states.async_set(
        'light.test', 'off', {'friendly_name': "Test light"})

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['brightness_pct'] == 50
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize(
    "result,adjust", [(25, '-5'), (35, '5'), (0, '-80')])
def test_api_adjust_brightness(hass, result, adjust):
    """Test api adjust brightness process."""
    request = get_new_request(
        'Alexa.BrightnessController', 'AdjustBrightness', 'light#test')

    # add payload
    request['directive']['payload']['brightnessDelta'] = adjust

    # setup test devices
    hass.states.async_set(
        'light.test', 'off', {
            'friendly_name': "Test light", 'brightness': '77'
        })

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['brightness_pct'] == result
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
def test_api_set_color_rgb(hass):
    """Test api set color process."""
    request = get_new_request(
        'Alexa.ColorController', 'SetColor', 'light#test')

    # add payload
    request['directive']['payload']['color'] = {
        'hue': '120',
        'saturation': '0.612',
        'brightness': '0.342',
    }

    # setup test devices
    hass.states.async_set(
        'light.test', 'off', {
            'friendly_name': "Test light",
            'supported_features': 16,
        })

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['rgb_color'] == (33, 87, 33)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
def test_api_set_color_xy(hass):
    """Test api set color process."""
    request = get_new_request(
        'Alexa.ColorController', 'SetColor', 'light#test')

    # add payload
    request['directive']['payload']['color'] = {
        'hue': '120',
        'saturation': '0.612',
        'brightness': '0.342',
    }

    # setup test devices
    hass.states.async_set(
        'light.test', 'off', {
            'friendly_name': "Test light",
            'supported_features': 64,
        })

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['xy_color'] == (0.23, 0.585)
    assert call_light[0].data['brightness'] == 18
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
def test_api_set_color_temperature(hass):
    """Test api set color temperature process."""
    request = get_new_request(
        'Alexa.ColorTemperatureController', 'SetColorTemperature',
        'light#test')

    # add payload
    request['directive']['payload']['colorTemperatureInKelvin'] = '7500'

    # setup test devices
    hass.states.async_set(
        'light.test', 'off', {'friendly_name': "Test light"})

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['kelvin'] == 7500
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("result,initial", [(383, '333'), (500, '500')])
def test_api_decrease_color_temp(hass, result, initial):
    """Test api decrease color temp process."""
    request = get_new_request(
        'Alexa.ColorTemperatureController', 'DecreaseColorTemperature',
        'light#test')

    # setup test devices
    hass.states.async_set(
        'light.test', 'off', {
            'friendly_name': "Test light", 'color_temp': initial,
            'max_mireds': 500,
        })

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['color_temp'] == result
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("result,initial", [(283, '333'), (142, '142')])
def test_api_increase_color_temp(hass, result, initial):
    """Test api increase color temp process."""
    request = get_new_request(
        'Alexa.ColorTemperatureController', 'IncreaseColorTemperature',
        'light#test')

    # setup test devices
    hass.states.async_set(
        'light.test', 'off', {
            'friendly_name': "Test light", 'color_temp': initial,
            'min_mireds': 142,
        })

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['color_temp'] == result
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['scene', 'group', 'script'])
def test_api_activate(hass, domain):
    """Test api activate process."""
    request = get_new_request(
        'Alexa.SceneController', 'Activate', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    if domain == 'group':
        call_domain = 'homeassistant'
    else:
        call_domain = domain

    call = async_mock_service(hass, call_domain, 'turn_on')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'ActivationStarted'
    assert msg['payload']['cause']['type'] == 'VOICE_INTERACTION'
    assert 'timestamp' in msg['payload']


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['group', 'script'])
def test_api_deactivate(hass, domain):
    """Test api deactivate process."""
    request = get_new_request(
        'Alexa.SceneController', 'Deactivate', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    if domain == 'group':
        call_domain = 'homeassistant'
    else:
        call_domain = domain

    call = async_mock_service(hass, call_domain, 'turn_off')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'DeactivationStarted'
    assert msg['payload']['cause']['type'] == 'VOICE_INTERACTION'
    assert 'timestamp' in msg['payload']


@asyncio.coroutine
def test_api_set_percentage_fan(hass):
    """Test api set percentage for fan process."""
    request = get_new_request(
        'Alexa.PercentageController', 'SetPercentage', 'fan#test_2')

    # add payload
    request['directive']['payload']['percentage'] = '50'

    # setup test devices
    hass.states.async_set(
        'fan.test_2', 'off', {'friendly_name': "Test fan"})

    call_fan = async_mock_service(hass, 'fan', 'set_speed')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_fan) == 1
    assert call_fan[0].data['entity_id'] == 'fan.test_2'
    assert call_fan[0].data['speed'] == 'medium'
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
def test_api_set_percentage_cover(hass):
    """Test api set percentage for cover process."""
    request = get_new_request(
        'Alexa.PercentageController', 'SetPercentage', 'cover#test')

    # add payload
    request['directive']['payload']['percentage'] = '50'

    # setup test devices
    hass.states.async_set(
        'cover.test', 'closed', {
            'friendly_name': "Test cover"
        })

    call_cover = async_mock_service(hass, 'cover', 'set_cover_position')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_cover) == 1
    assert call_cover[0].data['entity_id'] == 'cover.test'
    assert call_cover[0].data['position'] == 50
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize(
    "result,adjust", [('high', '-5'), ('off', '5'), ('low', '-80')])
def test_api_adjust_percentage_fan(hass, result, adjust):
    """Test api adjust percentage for fan process."""
    request = get_new_request(
        'Alexa.PercentageController', 'AdjustPercentage', 'fan#test_2')

    # add payload
    request['directive']['payload']['percentageDelta'] = adjust

    # setup test devices
    hass.states.async_set(
        'fan.test_2', 'on', {
            'friendly_name': "Test fan 2", 'speed': 'high'
        })

    call_fan = async_mock_service(hass, 'fan', 'set_speed')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_fan) == 1
    assert call_fan[0].data['entity_id'] == 'fan.test_2'
    assert call_fan[0].data['speed'] == result
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize(
    "result,adjust", [(25, '-5'), (35, '5'), (0, '-80')])
def test_api_adjust_percentage_cover(hass, result, adjust):
    """Test api adjust percentage for cover process."""
    request = get_new_request(
        'Alexa.PercentageController', 'AdjustPercentage', 'cover#test')

    # add payload
    request['directive']['payload']['percentageDelta'] = adjust

    # setup test devices
    hass.states.async_set(
        'cover.test', 'closed', {
            'friendly_name': "Test cover",
            'position': 30
        })

    call_cover = async_mock_service(hass, 'cover', 'set_cover_position')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_cover) == 1
    assert call_cover[0].data['entity_id'] == 'cover.test'
    assert call_cover[0].data['position'] == result
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['lock'])
def test_api_lock(hass, domain):
    """Test api lock process."""
    request = get_new_request(
        'Alexa.LockController', 'Lock', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'lock')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['media_player'])
def test_api_play(hass, domain):
    """Test api play process."""
    request = get_new_request(
        'Alexa.PlaybackController', 'Play', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'media_play')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['media_player'])
def test_api_pause(hass, domain):
    """Test api pause process."""
    request = get_new_request(
        'Alexa.PlaybackController', 'Pause', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'media_pause')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['media_player'])
def test_api_stop(hass, domain):
    """Test api stop process."""
    request = get_new_request(
        'Alexa.PlaybackController', 'Stop', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'media_stop')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['media_player'])
def test_api_next(hass, domain):
    """Test api next process."""
    request = get_new_request(
        'Alexa.PlaybackController', 'Next', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'media_next_track')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['media_player'])
def test_api_previous(hass, domain):
    """Test api previous process."""
    request = get_new_request(
        'Alexa.PlaybackController', 'Previous', '{}#test'.format(domain))

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'media_previous_track')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
def test_api_set_volume(hass):
    """Test api set volume process."""
    request = get_new_request(
        'Alexa.Speaker', 'SetVolume', 'media_player#test')

    # add payload
    request['directive']['payload']['volume'] = 50

    # setup test devices
    hass.states.async_set(
        'media_player.test', 'off', {
            'friendly_name': "Test media player", 'volume_level': 0
        })

    call_media_player = async_mock_service(hass, 'media_player', 'volume_set')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_media_player) == 1
    assert call_media_player[0].data['entity_id'] == 'media_player.test'
    assert call_media_player[0].data['volume_level'] == 0.5
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize(
    "result,adjust", [(0.7, '-5'), (0.8, '5'), (0, '-80')])
def test_api_adjust_volume(hass, result, adjust):
    """Test api adjust volume process."""
    request = get_new_request(
        'Alexa.Speaker', 'AdjustVolume', 'media_player#test')

    # add payload
    request['directive']['payload']['volume'] = adjust

    # setup test devices
    hass.states.async_set(
        'media_player.test', 'off', {
            'friendly_name': "Test media player", 'volume_level': 0.75
        })

    call_media_player = async_mock_service(hass, 'media_player', 'volume_set')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_media_player) == 1
    assert call_media_player[0].data['entity_id'] == 'media_player.test'
    assert call_media_player[0].data['volume_level'] == result
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['media_player'])
def test_api_mute(hass, domain):
    """Test api mute process."""
    request = get_new_request(
        'Alexa.Speaker', 'SetMute', '{}#test'.format(domain))

    request['directive']['payload']['mute'] = True

    # setup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'volume_mute')

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
def test_api_report_temperature(hass):
    """Test API ReportState response for a temperature sensor."""
    request = get_new_request('Alexa', 'ReportState', 'sensor#test')

    # setup test devices
    hass.states.async_set(
        'sensor.test', '42', {
            'friendly_name': 'test sensor',
            CONF_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT,
        })

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    header = msg['event']['header']
    assert header['namespace'] == 'Alexa'
    assert header['name'] == 'StateReport'

    properties = msg['context']['properties']
    assert len(properties) == 1
    prop = properties[0]
    assert prop['namespace'] == 'Alexa.TemperatureSensor'
    assert prop['name'] == 'temperature'
    assert prop['value'] == {'value': 42.0, 'scale': 'FAHRENHEIT'}


@asyncio.coroutine
def test_entity_config(hass):
    """Test that we can configure things via entity config."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    hass.states.async_set(
        'light.test_1', 'on', {'friendly_name': "Test light 1"})

    config = smart_home.Config(
        should_expose=lambda entity_id: True,
        entity_config={
            'light.test_1': {
                'name': 'Config name',
                'display_categories': 'SWITCH',
                'description': 'Config description'
            }
        }
    )

    msg = yield from smart_home.async_handle_message(
        hass, config, request)

    assert 'event' in msg
    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 1

    appliance = msg['payload']['endpoints'][0]
    assert appliance['endpointId'] == 'light#test_1'
    assert appliance['displayCategories'][0] == "SWITCH"
    assert appliance['friendlyName'] == "Config name"
    assert appliance['description'] == "Config description"
    assert len(appliance['capabilities']) == 1
    assert appliance['capabilities'][-1]['interface'] == \
        'Alexa.PowerController'


@asyncio.coroutine
def test_unsupported_domain(hass):
    """Discovery ignores entities of unknown domains."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    hass.states.async_set(
        'woz.boop', 'on', {'friendly_name': "Boop Woz"})

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)

    assert 'event' in msg
    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 0


@asyncio.coroutine
def do_http_discovery(config, hass, test_client):
    """Submit a request to the Smart Home HTTP API."""
    yield from async_setup_component(hass, alexa.DOMAIN, config)
    http_client = yield from test_client(hass.http.app)

    request = get_new_request('Alexa.Discovery', 'Discover')
    response = yield from http_client.post(
        smart_home.SMART_HOME_HTTP_ENDPOINT,
        data=json.dumps(request),
        headers={'content-type': 'application/json'})
    return response


@asyncio.coroutine
def test_http_api(hass, test_client):
    """With `smart_home:` HTTP API is exposed."""
    config = {
        'alexa': {
            'smart_home': None
        }
    }

    response = yield from do_http_discovery(config, hass, test_client)
    response_data = yield from response.json()

    # Here we're testing just the HTTP view glue -- details of discovery are
    # covered in other tests.
    assert response_data['event']['header']['name'] == 'Discover.Response'


@asyncio.coroutine
def test_http_api_disabled(hass, test_client):
    """Without `smart_home:`, the HTTP API is disabled."""
    config = {
        'alexa': {}
    }
    response = yield from do_http_discovery(config, hass, test_client)

    assert response.status == 404
