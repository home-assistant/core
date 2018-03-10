"""Test for smart home alexa support."""
import asyncio
import json
from uuid import uuid4

import pytest

from homeassistant.const import (
    TEMP_FAHRENHEIT, STATE_LOCKED, STATE_UNLOCKED,
    STATE_UNKNOWN)
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
def discovery_test(device, hass, expected_endpoints=1):
    """Test alexa discovery request."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # setup test devices
    hass.states.async_set(*device)

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['name'] == 'Discover.Response'
    assert msg['header']['namespace'] == 'Alexa.Discovery'
    endpoints = msg['payload']['endpoints']
    assert len(endpoints) == expected_endpoints

    if expected_endpoints == 1:
        return endpoints[0]
    elif expected_endpoints > 1:
        return endpoints
    return None


def assert_endpoint_capabilities(endpoint, *interfaces):
    """Assert the endpoint supports the given interfaces.

    Returns a set of capabilities, in case you want to assert more things about
    them.
    """
    capabilities = endpoint['capabilities']
    supported = set(
        feature['interface']
        for feature in capabilities)

    assert supported == set(interfaces)
    return capabilities


@asyncio.coroutine
def test_switch(hass):
    """Test switch discovery."""
    device = ('switch.test', 'on', {'friendly_name': "Test switch"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'switch#test'
    assert appliance['displayCategories'][0] == "SWITCH"
    assert appliance['friendlyName'] == "Test switch"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    yield from assert_power_controller_works(
        'switch#test',
        'switch.turn_on',
        'switch.turn_off',
        hass)

    properties = yield from reported_properties(hass, 'switch#test')
    properties.assert_equal('Alexa.PowerController', 'powerState', 'ON')


@asyncio.coroutine
def test_light(hass):
    """Test light discovery."""
    device = ('light.test_1', 'on', {'friendly_name': "Test light 1"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'light#test_1'
    assert appliance['displayCategories'][0] == "LIGHT"
    assert appliance['friendlyName'] == "Test light 1"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    yield from assert_power_controller_works(
        'light#test_1',
        'light.turn_on',
        'light.turn_off',
        hass)


@asyncio.coroutine
def test_dimmable_light(hass):
    """Test dimmable light discovery."""
    device = (
        'light.test_2', 'on', {
            'brightness': 128,
            'friendly_name': "Test light 2", 'supported_features': 1
        })
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'light#test_2'
    assert appliance['displayCategories'][0] == "LIGHT"
    assert appliance['friendlyName'] == "Test light 2"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.BrightnessController',
        'Alexa.PowerController',
    )

    properties = yield from reported_properties(hass, 'light#test_2')
    properties.assert_equal('Alexa.PowerController', 'powerState', 'ON')
    properties.assert_equal('Alexa.BrightnessController', 'brightness', 50)

    call, _ = yield from assert_request_calls_service(
        'Alexa.BrightnessController', 'SetBrightness', 'light#test_2',
        'light.turn_on',
        hass,
        payload={'brightness': '50'})
    assert call.data['brightness_pct'] == 50


@asyncio.coroutine
def test_color_light(hass):
    """Test color light discovery."""
    device = (
        'light.test_3',
        'on',
        {
            'friendly_name': "Test light 3",
            'supported_features': 19,
            'min_mireds': 142,
            'color_temp': '333',
        }
    )
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'light#test_3'
    assert appliance['displayCategories'][0] == "LIGHT"
    assert appliance['friendlyName'] == "Test light 3"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.BrightnessController',
        'Alexa.PowerController',
        'Alexa.ColorController',
        'Alexa.ColorTemperatureController',
    )

    # IncreaseColorTemperature and DecreaseColorTemperature have their own
    # tests


@asyncio.coroutine
def test_script(hass):
    """Test script discovery."""
    device = ('script.test', 'off', {'friendly_name': "Test script"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'script#test'
    assert appliance['displayCategories'][0] == "ACTIVITY_TRIGGER"
    assert appliance['friendlyName'] == "Test script"

    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.SceneController')
    assert not capability['supportsDeactivation']

    yield from assert_scene_controller_works(
        'script#test',
        'script.turn_on',
        None,
        hass)


@asyncio.coroutine
def test_cancelable_script(hass):
    """Test cancalable script discovery."""
    device = (
        'script.test_2',
        'off',
        {'friendly_name': "Test script 2", 'can_cancel': True},
    )
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'script#test_2'
    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.SceneController')
    assert capability['supportsDeactivation']

    yield from assert_scene_controller_works(
        'script#test_2',
        'script.turn_on',
        'script.turn_off',
        hass)


@asyncio.coroutine
def test_input_boolean(hass):
    """Test input boolean discovery."""
    device = (
        'input_boolean.test',
        'off',
        {'friendly_name': "Test input boolean"},
    )
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'input_boolean#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test input boolean"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    yield from assert_power_controller_works(
        'input_boolean#test',
        'input_boolean.turn_on',
        'input_boolean.turn_off',
        hass)


@asyncio.coroutine
def test_scene(hass):
    """Test scene discovery."""
    device = ('scene.test', 'off', {'friendly_name': "Test scene"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'scene#test'
    assert appliance['displayCategories'][0] == "SCENE_TRIGGER"
    assert appliance['friendlyName'] == "Test scene"

    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.SceneController')
    assert not capability['supportsDeactivation']

    yield from assert_scene_controller_works(
        'scene#test',
        'scene.turn_on',
        None,
        hass)


@asyncio.coroutine
def test_fan(hass):
    """Test fan discovery."""
    device = ('fan.test_1', 'off', {'friendly_name': "Test fan 1"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'fan#test_1'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test fan 1"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')


@asyncio.coroutine
def test_variable_fan(hass):
    """Test fan discovery.

    This one has variable speed.
    """
    device = (
        'fan.test_2',
        'off', {
            'friendly_name': "Test fan 2",
            'supported_features': 1,
            'speed_list': ['low', 'medium', 'high'],
            'speed': 'high',
        }
    )
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'fan#test_2'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test fan 2"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.PercentageController',
        'Alexa.PowerController',
    )

    call, _ = yield from assert_request_calls_service(
        'Alexa.PercentageController', 'SetPercentage', 'fan#test_2',
        'fan.set_speed',
        hass,
        payload={'percentage': '50'})
    assert call.data['speed'] == 'medium'

    yield from assert_percentage_changes(
        hass,
        [('high', '-5'), ('off', '5'), ('low', '-80')],
        'Alexa.PercentageController', 'AdjustPercentage', 'fan#test_2',
        'percentageDelta',
        'fan.set_speed',
        'speed')


@asyncio.coroutine
def test_lock(hass):
    """Test lock discovery."""
    device = ('lock.test', 'off', {'friendly_name': "Test lock"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'lock#test'
    assert appliance['displayCategories'][0] == "SMARTLOCK"
    assert appliance['friendlyName'] == "Test lock"
    assert_endpoint_capabilities(appliance, 'Alexa.LockController')

    _, msg = yield from assert_request_calls_service(
        'Alexa.LockController', 'Lock', 'lock#test',
        'lock.lock',
        hass)

    # always return LOCKED for now
    properties = msg['context']['properties'][0]
    assert properties['name'] == 'lockState'
    assert properties['namespace'] == 'Alexa.LockController'
    assert properties['value'] == 'LOCKED'


@asyncio.coroutine
def test_media_player(hass):
    """Test media player discovery."""
    device = (
        'media_player.test',
        'off', {
            'friendly_name': "Test media player",
            'supported_features': 0x59bd,
            'volume_level': 0.75
        }
    )
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'media_player#test'
    assert appliance['displayCategories'][0] == "TV"
    assert appliance['friendlyName'] == "Test media player"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.InputController',
        'Alexa.PowerController',
        'Alexa.Speaker',
        'Alexa.StepSpeaker',
        'Alexa.PlaybackController',
    )

    yield from assert_power_controller_works(
        'media_player#test',
        'media_player.turn_on',
        'media_player.turn_off',
        hass)

    yield from assert_request_calls_service(
        'Alexa.PlaybackController', 'Play', 'media_player#test',
        'media_player.media_play',
        hass)

    yield from assert_request_calls_service(
        'Alexa.PlaybackController', 'Pause', 'media_player#test',
        'media_player.media_pause',
        hass)

    yield from assert_request_calls_service(
        'Alexa.PlaybackController', 'Stop', 'media_player#test',
        'media_player.media_stop',
        hass)

    yield from assert_request_calls_service(
        'Alexa.PlaybackController', 'Next', 'media_player#test',
        'media_player.media_next_track',
        hass)

    yield from assert_request_calls_service(
        'Alexa.PlaybackController', 'Previous', 'media_player#test',
        'media_player.media_previous_track',
        hass)

    call, _ = yield from assert_request_calls_service(
        'Alexa.Speaker', 'SetVolume', 'media_player#test',
        'media_player.volume_set',
        hass,
        payload={'volume': 50})
    assert call.data['volume_level'] == 0.5

    call, _ = yield from assert_request_calls_service(
        'Alexa.Speaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': True})
    assert call.data['is_volume_muted']

    call, _, = yield from assert_request_calls_service(
        'Alexa.Speaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': False})
    assert not call.data['is_volume_muted']

    yield from assert_percentage_changes(
        hass,
        [(0.7, '-5'), (0.8, '5'), (0, '-80')],
        'Alexa.Speaker', 'AdjustVolume', 'media_player#test',
        'volume',
        'media_player.volume_set',
        'volume_level')

    call, _ = yield from assert_request_calls_service(
        'Alexa.StepSpeaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': True})
    assert call.data['is_volume_muted']

    call, _, = yield from assert_request_calls_service(
        'Alexa.StepSpeaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': False})
    assert not call.data['is_volume_muted']

    call, _ = yield from assert_request_calls_service(
        'Alexa.StepSpeaker', 'AdjustVolume', 'media_player#test',
        'media_player.volume_up',
        hass,
        payload={'volumeSteps': 20})

    call, _ = yield from assert_request_calls_service(
        'Alexa.StepSpeaker', 'AdjustVolume', 'media_player#test',
        'media_player.volume_down',
        hass,
        payload={'volumeSteps': -20})


@asyncio.coroutine
def test_alert(hass):
    """Test alert discovery."""
    device = ('alert.test', 'off', {'friendly_name': "Test alert"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'alert#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test alert"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    yield from assert_power_controller_works(
        'alert#test',
        'alert.turn_on',
        'alert.turn_off',
        hass)


@asyncio.coroutine
def test_automation(hass):
    """Test automation discovery."""
    device = ('automation.test', 'off', {'friendly_name': "Test automation"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'automation#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test automation"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    yield from assert_power_controller_works(
        'automation#test',
        'automation.turn_on',
        'automation.turn_off',
        hass)


@asyncio.coroutine
def test_group(hass):
    """Test group discovery."""
    device = ('group.test', 'off', {'friendly_name': "Test group"})
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'group#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test group"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    yield from assert_power_controller_works(
        'group#test',
        'homeassistant.turn_on',
        'homeassistant.turn_off',
        hass)


@asyncio.coroutine
def test_cover(hass):
    """Test cover discovery."""
    device = (
        'cover.test',
        'off', {
            'friendly_name': "Test cover",
            'supported_features': 255,
            'position': 30,
        }
    )
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'cover#test'
    assert appliance['displayCategories'][0] == "DOOR"
    assert appliance['friendlyName'] == "Test cover"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.PercentageController',
        'Alexa.PowerController',
    )

    yield from assert_power_controller_works(
        'cover#test',
        'cover.open_cover',
        'cover.close_cover',
        hass)

    call, _ = yield from assert_request_calls_service(
        'Alexa.PercentageController', 'SetPercentage', 'cover#test',
        'cover.set_cover_position',
        hass,
        payload={'percentage': '50'})
    assert call.data['position'] == 50

    yield from assert_percentage_changes(
        hass,
        [(25, '-5'), (35, '5'), (0, '-80')],
        'Alexa.PercentageController', 'AdjustPercentage', 'cover#test',
        'percentageDelta',
        'cover.set_cover_position',
        'position')


@asyncio.coroutine
def assert_percentage_changes(
        hass,
        adjustments,
        namespace,
        name,
        endpoint,
        parameter,
        service,
        changed_parameter):
    """Assert an API request making percentage changes works.

    AdjustPercentage, AdjustBrightness, etc. are examples of such requests.
    """
    for result_volume, adjustment in adjustments:
        if parameter:
            payload = {parameter: adjustment}
        else:
            payload = {}

        call, _ = yield from assert_request_calls_service(
            namespace, name, endpoint, service,
            hass,
            payload=payload)
        assert call.data[changed_parameter] == result_volume


@asyncio.coroutine
def test_temp_sensor(hass):
    """Test temperature sensor discovery."""
    device = (
        'sensor.test_temp',
        '42',
        {
            'friendly_name': "Test Temp Sensor",
            'unit_of_measurement': TEMP_FAHRENHEIT,
        }
    )
    appliance = yield from discovery_test(device, hass)

    assert appliance['endpointId'] == 'sensor#test_temp'
    assert appliance['displayCategories'][0] == 'TEMPERATURE_SENSOR'
    assert appliance['friendlyName'] == 'Test Temp Sensor'

    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.TemperatureSensor')
    assert capability['interface'] == 'Alexa.TemperatureSensor'
    properties = capability['properties']
    assert properties['retrievable'] is True
    assert {'name': 'temperature'} in properties['supported']

    properties = yield from reported_properties(hass, 'sensor#test_temp')
    properties.assert_equal('Alexa.TemperatureSensor', 'temperature',
                            {'value': 42.0, 'scale': 'FAHRENHEIT'})


@asyncio.coroutine
def test_unknown_sensor(hass):
    """Test sensors of unknown quantities are not discovered."""
    device = (
        'sensor.test_sickness', '0.1', {
            'friendly_name': "Test Space Sickness Sensor",
            'unit_of_measurement': 'garn',
        })
    yield from discovery_test(device, hass, expected_endpoints=0)


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

    assert not call_switch
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
def assert_request_fails(
        namespace,
        name,
        endpoint,
        service_not_called,
        hass,
        payload=None):
    """Assert an API request returns an ErrorResponse."""
    request = get_new_request(namespace, name, endpoint)
    if payload:
        request['directive']['payload'] = payload

    domain, service_name = service_not_called.split('.')
    call = async_mock_service(hass, domain, service_name)

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert not call
    assert 'event' in msg
    assert msg['event']['header']['name'] == 'ErrorResponse'

    return msg


@asyncio.coroutine
def assert_request_calls_service(
        namespace,
        name,
        endpoint,
        service,
        hass,
        response_type='Response',
        payload=None):
    """Assert an API request calls a hass service."""
    request = get_new_request(namespace, name, endpoint)
    if payload:
        request['directive']['payload'] = payload

    domain, service_name = service.split('.')
    call = async_mock_service(hass, domain, service_name)

    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()

    assert len(call) == 1
    assert 'event' in msg
    assert call[0].data['entity_id'] == endpoint.replace('#', '.')
    assert msg['event']['header']['name'] == response_type

    return call[0], msg


@asyncio.coroutine
def assert_power_controller_works(endpoint, on_service, off_service, hass):
    """Assert PowerController API requests work."""
    yield from assert_request_calls_service(
        'Alexa.PowerController', 'TurnOn', endpoint,
        on_service, hass)

    yield from assert_request_calls_service(
        'Alexa.PowerController', 'TurnOff', endpoint,
        off_service, hass)


@asyncio.coroutine
def assert_scene_controller_works(
        endpoint,
        activate_service,
        deactivate_service,
        hass):
    """Assert SceneController API requests work."""
    _, response = yield from assert_request_calls_service(
        'Alexa.SceneController', 'Activate', endpoint,
        activate_service, hass,
        response_type='ActivationStarted')
    assert response['event']['payload']['cause']['type'] == 'VOICE_INTERACTION'
    assert 'timestamp' in response['event']['payload']

    if deactivate_service:
        yield from assert_request_calls_service(
            'Alexa.SceneController', 'Deactivate', endpoint,
            deactivate_service, hass,
            response_type='DeactivationStarted')
        cause_type = response['event']['payload']['cause']['type']
        assert cause_type == 'VOICE_INTERACTION'
        assert 'timestamp' in response['event']['payload']


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
def test_report_lock_state(hass):
    """Test LockController implements lockState property."""
    hass.states.async_set(
        'lock.locked', STATE_LOCKED, {})
    hass.states.async_set(
        'lock.unlocked', STATE_UNLOCKED, {})
    hass.states.async_set(
        'lock.unknown', STATE_UNKNOWN, {})

    properties = yield from reported_properties(hass, 'lock.locked')
    properties.assert_equal('Alexa.LockController', 'lockState', 'LOCKED')

    properties = yield from reported_properties(hass, 'lock.unlocked')
    properties.assert_equal('Alexa.LockController', 'lockState', 'UNLOCKED')

    properties = yield from reported_properties(hass, 'lock.unknown')
    properties.assert_equal('Alexa.LockController', 'lockState', 'JAMMED')


@asyncio.coroutine
def test_report_dimmable_light_state(hass):
    """Test BrightnessController reports brightness correctly."""
    hass.states.async_set(
        'light.test_on', 'on', {'friendly_name': "Test light On",
                                'brightness': 128, 'supported_features': 1})
    hass.states.async_set(
        'light.test_off', 'off', {'friendly_name': "Test light Off",
                                  'supported_features': 1})

    properties = yield from reported_properties(hass, 'light.test_on')
    properties.assert_equal('Alexa.BrightnessController', 'brightness', 50)

    properties = yield from reported_properties(hass, 'light.test_off')
    properties.assert_equal('Alexa.BrightnessController', 'brightness', 0)


@asyncio.coroutine
def reported_properties(hass, endpoint):
    """Use ReportState to get properties and return them.

    The result is a _ReportedProperties instance, which has methods to make
    assertions about the properties.
    """
    request = get_new_request('Alexa', 'ReportState', endpoint)
    msg = yield from smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    yield from hass.async_block_till_done()
    return _ReportedProperties(msg['context']['properties'])


class _ReportedProperties(object):
    def __init__(self, properties):
        self.properties = properties

    def assert_equal(self, namespace, name, value):
        """Assert a property is equal to a given value."""
        for prop in self.properties:
            if prop['namespace'] == namespace and prop['name'] == name:
                assert prop['value'] == value
                return prop

        assert False, 'property %s:%s not in %r' % (
            namespace,
            name,
            self.properties,
        )


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

    assert not msg['payload']['endpoints']


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


@asyncio.coroutine
@pytest.mark.parametrize(
    "domain,payload,source_list,idx", [
        ('media_player', 'GAME CONSOLE', ['tv', 'game console'], 1),
        ('media_player', 'SATELLITE TV', ['satellite-tv', 'game console'], 0),
        ('media_player', 'SATELLITE TV', ['satellite_tv', 'game console'], 0),
        ('media_player', 'BAD DEVICE', ['satellite_tv', 'game console'], None),
    ]
)
def test_api_select_input(hass, domain, payload, source_list, idx):
    """Test api set input process."""
    hass.states.async_set(
        'media_player.test', 'off', {
            'friendly_name': "Test media player",
            'source': 'unknown',
            'source_list': source_list,
        })

    # test where no source matches
    if idx is None:
        yield from assert_request_fails(
            'Alexa.InputController', 'SelectInput', 'media_player#test',
            'media_player.select_source',
            hass,
            payload={'input': payload})
        return

    call, _ = yield from assert_request_calls_service(
        'Alexa.InputController', 'SelectInput', 'media_player#test',
        'media_player.select_source',
        hass,
        payload={'input': payload})
    assert call.data['source'] == source_list[idx]
