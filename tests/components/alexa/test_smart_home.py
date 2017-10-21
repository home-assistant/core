"""Test for smart home alexa support."""
import asyncio
from uuid import uuid4

import pytest

from homeassistant.components.alexa import smart_home

from tests.common import async_mock_service


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
        yield from smart_home.async_handle_message(hass, msg)


@asyncio.coroutine
def test_discovery_request(hass):
    """Test alexa discovery request."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # settup test devices
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})

    hass.states.async_set(
        'light.test_1', 'on', {'friendly_name': "Test light 1"})
    hass.states.async_set(
        'light.test_2', 'on', {
            'friendly_name': "Test light 2", 'supported_features': 1
        })

    msg = yield from smart_home.async_handle_message(hass, request)

    assert 'event' in msg
    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 3
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

        raise AssertionError("Unknown appliance!")


@asyncio.coroutine
def test_api_entity_not_exists(hass):
    """Test api turn on process without entity."""
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#test')

    call_switch = async_mock_service(hass, 'switch', 'turn_on')

    msg = yield from smart_home.async_handle_message(hass, request)

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
    msg = yield from smart_home.async_handle_message(hass, request)

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['name'] == 'ErrorResponse'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['payload']['type'] == 'INTERNAL_ERROR'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['light', 'switch'])
def test_api_turn_on(hass, domain):
    """Test api turn on process."""
    request = get_new_request(
        'Alexa.PowerController', 'TurnOn', '{}#test'.format(domain))

    # settup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'off', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'turn_on')

    msg = yield from smart_home.async_handle_message(hass, request)

    assert 'event' in msg
    msg = msg['event']

    assert len(call) == 1
    assert call[0].data['entity_id'] == '{}.test'.format(domain)
    assert msg['header']['name'] == 'Response'


@asyncio.coroutine
@pytest.mark.parametrize("domain", ['light', 'switch'])
def test_api_turn_off(hass, domain):
    """Test api turn on process."""
    request = get_new_request(
        'Alexa.PowerController', 'TurnOff', '{}#test'.format(domain))

    # settup test devices
    hass.states.async_set(
        '{}.test'.format(domain), 'on', {
            'friendly_name': "Test {}".format(domain)
        })

    call = async_mock_service(hass, domain, 'turn_off')

    msg = yield from smart_home.async_handle_message(hass, request)

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

    # settup test devices
    hass.states.async_set(
        'light.test', 'off', {'friendly_name': "Test light"})

    call_light = async_mock_service(hass, 'light', 'turn_on')

    msg = yield from smart_home.async_handle_message(hass, request)

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['brightness'] == '50'
    assert msg['header']['name'] == 'Response'
