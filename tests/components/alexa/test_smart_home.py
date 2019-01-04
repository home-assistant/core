"""Test for smart home alexa support."""
import json
from uuid import uuid4

import pytest

from homeassistant.core import Context, callback
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, STATE_LOCKED,
    STATE_UNLOCKED, STATE_UNKNOWN)
from homeassistant.setup import async_setup_component
from homeassistant.components import alexa
from homeassistant.components.alexa import smart_home
from homeassistant.components.alexa.auth import Auth
from homeassistant.helpers import entityfilter

from tests.common import async_mock_service


async def get_access_token():
    """Return a test access token."""
    return "thisisnotanacesstoken"


TEST_URL = "https://api.amazonalexa.com/v3/events"
TEST_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

DEFAULT_CONFIG = smart_home.Config(
    endpoint=TEST_URL,
    async_get_access_token=get_access_token,
    should_expose=lambda entity_id: True)


@pytest.fixture
def events(hass):
    """Fixture that catches alexa events."""
    events = []
    hass.bus.async_listen(
        smart_home.EVENT_ALEXA_SMART_HOME,
        callback(lambda e: events.append(e))
    )
    yield events


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


def test_create_api_message_defaults(hass):
    """Create a API message response of a request with defaults."""
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#xy')
    directive_header = request['directive']['header']
    directive = smart_home._AlexaDirective(request)

    msg = directive.response(payload={'test': 3})._response

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['messageId'] is not None
    assert msg['header']['messageId'] != directive_header['messageId']
    assert msg['header']['correlationToken'] == \
        directive_header['correlationToken']
    assert msg['header']['name'] == 'Response'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['header']['payloadVersion'] == '3'

    assert 'test' in msg['payload']
    assert msg['payload']['test'] == 3

    assert msg['endpoint'] == request['directive']['endpoint']
    assert msg['endpoint'] is not request['directive']['endpoint']


def test_create_api_message_special():
    """Create a API message response of a request with non defaults."""
    request = get_new_request('Alexa.PowerController', 'TurnOn')
    directive_header = request['directive']['header']
    directive_header.pop('correlationToken')
    directive = smart_home._AlexaDirective(request)

    msg = directive.response('testName', 'testNameSpace')._response

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['messageId'] is not None
    assert msg['header']['messageId'] != directive_header['messageId']
    assert 'correlationToken' not in msg['header']
    assert msg['header']['name'] == 'testName'
    assert msg['header']['namespace'] == 'testNameSpace'
    assert msg['header']['payloadVersion'] == '3'

    assert msg['payload'] == {}
    assert 'endpoint' not in msg


async def test_wrong_version(hass):
    """Test with wrong version."""
    msg = get_new_request('Alexa.PowerController', 'TurnOn')
    msg['directive']['header']['payloadVersion'] = '2'

    with pytest.raises(AssertionError):
        await smart_home.async_handle_message(hass, DEFAULT_CONFIG, msg)


async def discovery_test(device, hass, expected_endpoints=1):
    """Test alexa discovery request."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # setup test devices
    hass.states.async_set(*device)

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['name'] == 'Discover.Response'
    assert msg['header']['namespace'] == 'Alexa.Discovery'
    endpoints = msg['payload']['endpoints']
    assert len(endpoints) == expected_endpoints

    if expected_endpoints == 1:
        return endpoints[0]
    if expected_endpoints > 1:
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


async def test_switch(hass, events):
    """Test switch discovery."""
    device = ('switch.test', 'on', {'friendly_name': "Test switch"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'switch#test'
    assert appliance['displayCategories'][0] == "SWITCH"
    assert appliance['friendlyName'] == "Test switch"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    await assert_power_controller_works(
        'switch#test',
        'switch.turn_on',
        'switch.turn_off',
        hass)

    properties = await reported_properties(hass, 'switch#test')
    properties.assert_equal('Alexa.PowerController', 'powerState', 'ON')


async def test_light(hass):
    """Test light discovery."""
    device = ('light.test_1', 'on', {'friendly_name': "Test light 1"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'light#test_1'
    assert appliance['displayCategories'][0] == "LIGHT"
    assert appliance['friendlyName'] == "Test light 1"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    await assert_power_controller_works(
        'light#test_1',
        'light.turn_on',
        'light.turn_off',
        hass)


async def test_dimmable_light(hass):
    """Test dimmable light discovery."""
    device = (
        'light.test_2', 'on', {
            'brightness': 128,
            'friendly_name': "Test light 2", 'supported_features': 1
        })
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'light#test_2'
    assert appliance['displayCategories'][0] == "LIGHT"
    assert appliance['friendlyName'] == "Test light 2"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.BrightnessController',
        'Alexa.PowerController',
    )

    properties = await reported_properties(hass, 'light#test_2')
    properties.assert_equal('Alexa.PowerController', 'powerState', 'ON')
    properties.assert_equal('Alexa.BrightnessController', 'brightness', 50)

    call, _ = await assert_request_calls_service(
        'Alexa.BrightnessController', 'SetBrightness', 'light#test_2',
        'light.turn_on',
        hass,
        payload={'brightness': '50'})
    assert call.data['brightness_pct'] == 50


async def test_color_light(hass):
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
    appliance = await discovery_test(device, hass)

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


async def test_script(hass):
    """Test script discovery."""
    device = ('script.test', 'off', {'friendly_name': "Test script"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'script#test'
    assert appliance['displayCategories'][0] == "ACTIVITY_TRIGGER"
    assert appliance['friendlyName'] == "Test script"

    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.SceneController')
    assert not capability['supportsDeactivation']

    await assert_scene_controller_works(
        'script#test',
        'script.turn_on',
        None,
        hass)


async def test_cancelable_script(hass):
    """Test cancalable script discovery."""
    device = (
        'script.test_2',
        'off',
        {'friendly_name': "Test script 2", 'can_cancel': True},
    )
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'script#test_2'
    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.SceneController')
    assert capability['supportsDeactivation']

    await assert_scene_controller_works(
        'script#test_2',
        'script.turn_on',
        'script.turn_off',
        hass)


async def test_input_boolean(hass):
    """Test input boolean discovery."""
    device = (
        'input_boolean.test',
        'off',
        {'friendly_name': "Test input boolean"},
    )
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'input_boolean#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test input boolean"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    await assert_power_controller_works(
        'input_boolean#test',
        'input_boolean.turn_on',
        'input_boolean.turn_off',
        hass)


async def test_scene(hass):
    """Test scene discovery."""
    device = ('scene.test', 'off', {'friendly_name': "Test scene"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'scene#test'
    assert appliance['displayCategories'][0] == "SCENE_TRIGGER"
    assert appliance['friendlyName'] == "Test scene"

    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.SceneController')
    assert not capability['supportsDeactivation']

    await assert_scene_controller_works(
        'scene#test',
        'scene.turn_on',
        None,
        hass)


async def test_fan(hass):
    """Test fan discovery."""
    device = ('fan.test_1', 'off', {'friendly_name': "Test fan 1"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'fan#test_1'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test fan 1"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')


async def test_variable_fan(hass):
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
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'fan#test_2'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test fan 2"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.PercentageController',
        'Alexa.PowerController',
    )

    call, _ = await assert_request_calls_service(
        'Alexa.PercentageController', 'SetPercentage', 'fan#test_2',
        'fan.set_speed',
        hass,
        payload={'percentage': '50'})
    assert call.data['speed'] == 'medium'

    await assert_percentage_changes(
        hass,
        [('high', '-5'), ('off', '5'), ('low', '-80')],
        'Alexa.PercentageController', 'AdjustPercentage', 'fan#test_2',
        'percentageDelta',
        'fan.set_speed',
        'speed')


async def test_lock(hass):
    """Test lock discovery."""
    device = ('lock.test', 'off', {'friendly_name': "Test lock"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'lock#test'
    assert appliance['displayCategories'][0] == "SMARTLOCK"
    assert appliance['friendlyName'] == "Test lock"
    assert_endpoint_capabilities(appliance, 'Alexa.LockController')

    _, msg = await assert_request_calls_service(
        'Alexa.LockController', 'Lock', 'lock#test',
        'lock.lock',
        hass)

    # always return LOCKED for now
    properties = msg['context']['properties'][0]
    assert properties['name'] == 'lockState'
    assert properties['namespace'] == 'Alexa.LockController'
    assert properties['value'] == 'LOCKED'


async def test_media_player(hass):
    """Test media player discovery."""
    device = (
        'media_player.test',
        'off', {
            'friendly_name': "Test media player",
            'supported_features': 0x59bd,
            'volume_level': 0.75
        }
    )
    appliance = await discovery_test(device, hass)

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

    await assert_power_controller_works(
        'media_player#test',
        'media_player.turn_on',
        'media_player.turn_off',
        hass)

    await assert_request_calls_service(
        'Alexa.PlaybackController', 'Play', 'media_player#test',
        'media_player.media_play',
        hass)

    await assert_request_calls_service(
        'Alexa.PlaybackController', 'Pause', 'media_player#test',
        'media_player.media_pause',
        hass)

    await assert_request_calls_service(
        'Alexa.PlaybackController', 'Stop', 'media_player#test',
        'media_player.media_stop',
        hass)

    await assert_request_calls_service(
        'Alexa.PlaybackController', 'Next', 'media_player#test',
        'media_player.media_next_track',
        hass)

    await assert_request_calls_service(
        'Alexa.PlaybackController', 'Previous', 'media_player#test',
        'media_player.media_previous_track',
        hass)

    call, _ = await assert_request_calls_service(
        'Alexa.Speaker', 'SetVolume', 'media_player#test',
        'media_player.volume_set',
        hass,
        payload={'volume': 50})
    assert call.data['volume_level'] == 0.5

    call, _ = await assert_request_calls_service(
        'Alexa.Speaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': True})
    assert call.data['is_volume_muted']

    call, _, = await assert_request_calls_service(
        'Alexa.Speaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': False})
    assert not call.data['is_volume_muted']

    await assert_percentage_changes(
        hass,
        [(0.7, '-5'), (0.8, '5'), (0, '-80')],
        'Alexa.Speaker', 'AdjustVolume', 'media_player#test',
        'volume',
        'media_player.volume_set',
        'volume_level')

    call, _ = await assert_request_calls_service(
        'Alexa.StepSpeaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': True})
    assert call.data['is_volume_muted']

    call, _, = await assert_request_calls_service(
        'Alexa.StepSpeaker', 'SetMute', 'media_player#test',
        'media_player.volume_mute',
        hass,
        payload={'mute': False})
    assert not call.data['is_volume_muted']

    call, _ = await assert_request_calls_service(
        'Alexa.StepSpeaker', 'AdjustVolume', 'media_player#test',
        'media_player.volume_up',
        hass,
        payload={'volumeSteps': 20})

    call, _ = await assert_request_calls_service(
        'Alexa.StepSpeaker', 'AdjustVolume', 'media_player#test',
        'media_player.volume_down',
        hass,
        payload={'volumeSteps': -20})


async def test_alert(hass):
    """Test alert discovery."""
    device = ('alert.test', 'off', {'friendly_name': "Test alert"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'alert#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test alert"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    await assert_power_controller_works(
        'alert#test',
        'alert.turn_on',
        'alert.turn_off',
        hass)


async def test_automation(hass):
    """Test automation discovery."""
    device = ('automation.test', 'off', {'friendly_name': "Test automation"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'automation#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test automation"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    await assert_power_controller_works(
        'automation#test',
        'automation.turn_on',
        'automation.turn_off',
        hass)


async def test_group(hass):
    """Test group discovery."""
    device = ('group.test', 'off', {'friendly_name': "Test group"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'group#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test group"
    assert_endpoint_capabilities(appliance, 'Alexa.PowerController')

    await assert_power_controller_works(
        'group#test',
        'homeassistant.turn_on',
        'homeassistant.turn_off',
        hass)


async def test_cover(hass):
    """Test cover discovery."""
    device = (
        'cover.test',
        'off', {
            'friendly_name': "Test cover",
            'supported_features': 255,
            'position': 30,
        }
    )
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'cover#test'
    assert appliance['displayCategories'][0] == "DOOR"
    assert appliance['friendlyName'] == "Test cover"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.PercentageController',
        'Alexa.PowerController',
    )

    await assert_power_controller_works(
        'cover#test',
        'cover.open_cover',
        'cover.close_cover',
        hass)

    call, _ = await assert_request_calls_service(
        'Alexa.PercentageController', 'SetPercentage', 'cover#test',
        'cover.set_cover_position',
        hass,
        payload={'percentage': '50'})
    assert call.data['position'] == 50

    await assert_percentage_changes(
        hass,
        [(25, '-5'), (35, '5'), (0, '-80')],
        'Alexa.PercentageController', 'AdjustPercentage', 'cover#test',
        'percentageDelta',
        'cover.set_cover_position',
        'position')


async def assert_percentage_changes(
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

        call, _ = await assert_request_calls_service(
            namespace, name, endpoint, service,
            hass,
            payload=payload)
        assert call.data[changed_parameter] == result_volume


async def test_temp_sensor(hass):
    """Test temperature sensor discovery."""
    device = (
        'sensor.test_temp',
        '42',
        {
            'friendly_name': "Test Temp Sensor",
            'unit_of_measurement': TEMP_FAHRENHEIT,
        }
    )
    appliance = await discovery_test(device, hass)

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

    properties = await reported_properties(hass, 'sensor#test_temp')
    properties.assert_equal('Alexa.TemperatureSensor', 'temperature',
                            {'value': 42.0, 'scale': 'FAHRENHEIT'})


async def test_contact_sensor(hass):
    """Test contact sensor discovery."""
    device = (
        'binary_sensor.test_contact',
        'on',
        {
            'friendly_name': "Test Contact Sensor",
            'device_class': 'door',
        }
    )
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'binary_sensor#test_contact'
    assert appliance['displayCategories'][0] == 'CONTACT_SENSOR'
    assert appliance['friendlyName'] == 'Test Contact Sensor'

    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.ContactSensor')
    assert capability['interface'] == 'Alexa.ContactSensor'
    properties = capability['properties']
    assert properties['retrievable'] is True
    assert {'name': 'detectionState'} in properties['supported']

    properties = await reported_properties(hass,
                                           'binary_sensor#test_contact')
    properties.assert_equal('Alexa.ContactSensor', 'detectionState',
                            'DETECTED')


async def test_motion_sensor(hass):
    """Test motion sensor discovery."""
    device = (
        'binary_sensor.test_motion',
        'on',
        {
            'friendly_name': "Test Motion Sensor",
            'device_class': 'motion',
        }
    )
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'binary_sensor#test_motion'
    assert appliance['displayCategories'][0] == 'MOTION_SENSOR'
    assert appliance['friendlyName'] == 'Test Motion Sensor'

    (capability,) = assert_endpoint_capabilities(
        appliance,
        'Alexa.MotionSensor')
    assert capability['interface'] == 'Alexa.MotionSensor'
    properties = capability['properties']
    assert properties['retrievable'] is True
    assert {'name': 'detectionState'} in properties['supported']

    properties = await reported_properties(hass,
                                           'binary_sensor#test_motion')
    properties.assert_equal('Alexa.MotionSensor', 'detectionState',
                            'DETECTED')


async def test_unknown_sensor(hass):
    """Test sensors of unknown quantities are not discovered."""
    device = (
        'sensor.test_sickness', '0.1', {
            'friendly_name': "Test Space Sickness Sensor",
            'unit_of_measurement': 'garn',
        })
    await discovery_test(device, hass, expected_endpoints=0)


async def test_thermostat(hass):
    """Test thermostat discovery."""
    hass.config.units.temperature_unit = TEMP_FAHRENHEIT
    device = (
        'climate.test_thermostat',
        'cool',
        {
            'operation_mode': 'cool',
            'temperature': 70.0,
            'target_temp_high': 80.0,
            'target_temp_low': 60.0,
            'current_temperature': 75.0,
            'friendly_name': "Test Thermostat",
            'supported_features': 1 | 2 | 4 | 128,
            'operation_list': ['heat', 'cool', 'auto', 'off'],
            'min_temp': 50,
            'max_temp': 90,
        }
    )
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'climate#test_thermostat'
    assert appliance['displayCategories'][0] == 'THERMOSTAT'
    assert appliance['friendlyName'] == "Test Thermostat"

    assert_endpoint_capabilities(
        appliance,
        'Alexa.ThermostatController',
        'Alexa.TemperatureSensor',
    )

    properties = await reported_properties(
        hass, 'climate#test_thermostat')
    properties.assert_equal(
        'Alexa.ThermostatController', 'thermostatMode', 'COOL')
    properties.assert_equal(
        'Alexa.ThermostatController', 'targetSetpoint',
        {'value': 70.0, 'scale': 'FAHRENHEIT'})
    properties.assert_equal(
        'Alexa.TemperatureSensor', 'temperature',
        {'value': 75.0, 'scale': 'FAHRENHEIT'})

    call, msg = await assert_request_calls_service(
        'Alexa.ThermostatController', 'SetTargetTemperature',
        'climate#test_thermostat', 'climate.set_temperature',
        hass,
        payload={'targetSetpoint': {'value': 69.0, 'scale': 'FAHRENHEIT'}}
    )
    assert call.data['temperature'] == 69.0
    properties = _ReportedProperties(msg['context']['properties'])
    properties.assert_equal(
        'Alexa.ThermostatController', 'targetSetpoint',
        {'value': 69.0, 'scale': 'FAHRENHEIT'})

    msg = await assert_request_fails(
        'Alexa.ThermostatController', 'SetTargetTemperature',
        'climate#test_thermostat', 'climate.set_temperature',
        hass,
        payload={'targetSetpoint': {'value': 0.0, 'scale': 'CELSIUS'}}
    )
    assert msg['event']['payload']['type'] == 'TEMPERATURE_VALUE_OUT_OF_RANGE'

    call, msg = await assert_request_calls_service(
        'Alexa.ThermostatController', 'SetTargetTemperature',
        'climate#test_thermostat', 'climate.set_temperature',
        hass,
        payload={
            'targetSetpoint': {'value': 70.0, 'scale': 'FAHRENHEIT'},
            'lowerSetpoint': {'value': 293.15, 'scale': 'KELVIN'},
            'upperSetpoint': {'value': 30.0, 'scale': 'CELSIUS'},
        }
    )
    assert call.data['temperature'] == 70.0
    assert call.data['target_temp_low'] == 68.0
    assert call.data['target_temp_high'] == 86.0
    properties = _ReportedProperties(msg['context']['properties'])
    properties.assert_equal(
        'Alexa.ThermostatController', 'targetSetpoint',
        {'value': 70.0, 'scale': 'FAHRENHEIT'})
    properties.assert_equal(
        'Alexa.ThermostatController', 'lowerSetpoint',
        {'value': 68.0, 'scale': 'FAHRENHEIT'})
    properties.assert_equal(
        'Alexa.ThermostatController', 'upperSetpoint',
        {'value': 86.0, 'scale': 'FAHRENHEIT'})

    msg = await assert_request_fails(
        'Alexa.ThermostatController', 'SetTargetTemperature',
        'climate#test_thermostat', 'climate.set_temperature',
        hass,
        payload={
            'lowerSetpoint': {'value': 273.15, 'scale': 'KELVIN'},
            'upperSetpoint': {'value': 75.0, 'scale': 'FAHRENHEIT'},
        }
    )
    assert msg['event']['payload']['type'] == 'TEMPERATURE_VALUE_OUT_OF_RANGE'

    msg = await assert_request_fails(
        'Alexa.ThermostatController', 'SetTargetTemperature',
        'climate#test_thermostat', 'climate.set_temperature',
        hass,
        payload={
            'lowerSetpoint': {'value': 293.15, 'scale': 'FAHRENHEIT'},
            'upperSetpoint': {'value': 75.0, 'scale': 'CELSIUS'},
        }
    )
    assert msg['event']['payload']['type'] == 'TEMPERATURE_VALUE_OUT_OF_RANGE'

    call, msg = await assert_request_calls_service(
        'Alexa.ThermostatController', 'AdjustTargetTemperature',
        'climate#test_thermostat', 'climate.set_temperature',
        hass,
        payload={'targetSetpointDelta': {'value': -10.0, 'scale': 'KELVIN'}}
    )
    assert call.data['temperature'] == 52.0
    properties = _ReportedProperties(msg['context']['properties'])
    properties.assert_equal(
        'Alexa.ThermostatController', 'targetSetpoint',
        {'value': 52.0, 'scale': 'FAHRENHEIT'})

    msg = await assert_request_fails(
        'Alexa.ThermostatController', 'AdjustTargetTemperature',
        'climate#test_thermostat', 'climate.set_temperature',
        hass,
        payload={'targetSetpointDelta': {'value': 20.0, 'scale': 'CELSIUS'}}
    )
    assert msg['event']['payload']['type'] == 'TEMPERATURE_VALUE_OUT_OF_RANGE'

    # Setting mode, the payload can be an object with a value attribute...
    call, msg = await assert_request_calls_service(
        'Alexa.ThermostatController', 'SetThermostatMode',
        'climate#test_thermostat', 'climate.set_operation_mode',
        hass,
        payload={'thermostatMode': {'value': 'HEAT'}}
    )
    assert call.data['operation_mode'] == 'heat'
    properties = _ReportedProperties(msg['context']['properties'])
    properties.assert_equal(
        'Alexa.ThermostatController', 'thermostatMode', 'HEAT')

    call, msg = await assert_request_calls_service(
        'Alexa.ThermostatController', 'SetThermostatMode',
        'climate#test_thermostat', 'climate.set_operation_mode',
        hass,
        payload={'thermostatMode': {'value': 'COOL'}}
    )
    assert call.data['operation_mode'] == 'cool'
    properties = _ReportedProperties(msg['context']['properties'])
    properties.assert_equal(
        'Alexa.ThermostatController', 'thermostatMode', 'COOL')

    # ...it can also be just the mode.
    call, msg = await assert_request_calls_service(
        'Alexa.ThermostatController', 'SetThermostatMode',
        'climate#test_thermostat', 'climate.set_operation_mode',
        hass,
        payload={'thermostatMode': 'HEAT'}
    )
    assert call.data['operation_mode'] == 'heat'
    properties = _ReportedProperties(msg['context']['properties'])
    properties.assert_equal(
        'Alexa.ThermostatController', 'thermostatMode', 'HEAT')

    msg = await assert_request_fails(
        'Alexa.ThermostatController', 'SetThermostatMode',
        'climate#test_thermostat', 'climate.set_operation_mode',
        hass,
        payload={'thermostatMode': {'value': 'INVALID'}}
    )
    assert msg['event']['payload']['type'] == 'UNSUPPORTED_THERMOSTAT_MODE'
    hass.config.units.temperature_unit = TEMP_CELSIUS

    call, _ = await assert_request_calls_service(
        'Alexa.ThermostatController', 'SetThermostatMode',
        'climate#test_thermostat', 'climate.set_operation_mode',
        hass,
        payload={'thermostatMode': 'OFF'}
    )
    assert call.data['operation_mode'] == 'off'


async def test_exclude_filters(hass):
    """Test exclusion filters."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # setup test devices
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})

    hass.states.async_set(
        'script.deny', 'off', {'friendly_name': "Blocked script"})

    hass.states.async_set(
        'cover.deny', 'off', {'friendly_name': "Blocked cover"})

    config = smart_home.Config(
        endpoint=None,
        async_get_access_token=None,
        should_expose=entityfilter.generate_filter(
            include_domains=[],
            include_entities=[],
            exclude_domains=['script'],
            exclude_entities=['cover.deny'],
        ))

    msg = await smart_home.async_handle_message(hass, config, request)
    await hass.async_block_till_done()

    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 1


async def test_include_filters(hass):
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

    config = smart_home.Config(
        endpoint=None,
        async_get_access_token=None,
        should_expose=entityfilter.generate_filter(
            include_domains=['automation', 'group'],
            include_entities=['script.deny'],
            exclude_domains=[],
            exclude_entities=[],
        ))

    msg = await smart_home.async_handle_message(hass, config, request)
    await hass.async_block_till_done()

    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 3


async def test_never_exposed_entities(hass):
    """Test never exposed locks do not get discovered."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    # setup test devices
    hass.states.async_set(
        'group.all_locks', 'on', {'friendly_name': "Blocked locks"})

    hass.states.async_set(
        'group.allow', 'off', {'friendly_name': "Allowed group"})

    config = smart_home.Config(
        endpoint=None,
        async_get_access_token=None,
        should_expose=entityfilter.generate_filter(
            include_domains=['group'],
            include_entities=[],
            exclude_domains=[],
            exclude_entities=[],
        ))

    msg = await smart_home.async_handle_message(hass, config, request)
    await hass.async_block_till_done()

    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 1


async def test_api_entity_not_exists(hass):
    """Test api turn on process without entity."""
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#test')

    call_switch = async_mock_service(hass, 'switch', 'turn_on')

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert not call_switch
    assert msg['header']['name'] == 'ErrorResponse'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['payload']['type'] == 'NO_SUCH_ENDPOINT'


async def test_api_function_not_implemented(hass):
    """Test api call that is not implemented to us."""
    request = get_new_request('Alexa.HAHAAH', 'Sweet')
    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['name'] == 'ErrorResponse'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['payload']['type'] == 'INTERNAL_ERROR'


async def assert_request_fails(
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

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert not call
    assert 'event' in msg
    assert msg['event']['header']['name'] == 'ErrorResponse'

    return msg


async def assert_request_calls_service(
        namespace,
        name,
        endpoint,
        service,
        hass,
        response_type='Response',
        payload=None):
    """Assert an API request calls a hass service."""
    context = Context()
    request = get_new_request(namespace, name, endpoint)
    if payload:
        request['directive']['payload'] = payload

    domain, service_name = service.split('.')
    calls = async_mock_service(hass, domain, service_name)

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request, context)
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert 'event' in msg
    assert call.data['entity_id'] == endpoint.replace('#', '.')
    assert msg['event']['header']['name'] == response_type
    assert call.context == context

    return call, msg


async def assert_power_controller_works(
    endpoint,
    on_service,
    off_service,
    hass
):
    """Assert PowerController API requests work."""
    await assert_request_calls_service(
        'Alexa.PowerController', 'TurnOn', endpoint,
        on_service, hass)

    await assert_request_calls_service(
        'Alexa.PowerController', 'TurnOff', endpoint,
        off_service, hass)


async def assert_scene_controller_works(
        endpoint,
        activate_service,
        deactivate_service,
        hass):
    """Assert SceneController API requests work."""
    _, response = await assert_request_calls_service(
        'Alexa.SceneController', 'Activate', endpoint,
        activate_service, hass,
        response_type='ActivationStarted')
    assert response['event']['payload']['cause']['type'] == 'VOICE_INTERACTION'
    assert 'timestamp' in response['event']['payload']

    if deactivate_service:
        await assert_request_calls_service(
            'Alexa.SceneController', 'Deactivate', endpoint,
            deactivate_service, hass,
            response_type='DeactivationStarted')
        cause_type = response['event']['payload']['cause']['type']
        assert cause_type == 'VOICE_INTERACTION'
        assert 'timestamp' in response['event']['payload']


@pytest.mark.parametrize(
    "result,adjust", [(25, '-5'), (35, '5'), (0, '-80')])
async def test_api_adjust_brightness(hass, result, adjust):
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

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['brightness_pct'] == result
    assert msg['header']['name'] == 'Response'


async def test_api_set_color_rgb(hass):
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

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['rgb_color'] == (33, 87, 33)
    assert msg['header']['name'] == 'Response'


async def test_api_set_color_temperature(hass):
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

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['kelvin'] == 7500
    assert msg['header']['name'] == 'Response'


@pytest.mark.parametrize("result,initial", [(383, '333'), (500, '500')])
async def test_api_decrease_color_temp(hass, result, initial):
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

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['color_temp'] == result
    assert msg['header']['name'] == 'Response'


@pytest.mark.parametrize("result,initial", [(283, '333'), (142, '142')])
async def test_api_increase_color_temp(hass, result, initial):
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

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert len(call_light) == 1
    assert call_light[0].data['entity_id'] == 'light.test'
    assert call_light[0].data['color_temp'] == result
    assert msg['header']['name'] == 'Response'


async def test_api_accept_grant(hass):
    """Test api AcceptGrant process."""
    request = get_new_request("Alexa.Authorization", "AcceptGrant")

    # add payload
    request['directive']['payload'] = {
      'grant': {
        'type': 'OAuth2.AuthorizationCode',
        'code': 'VGhpcyBpcyBhbiBhdXRob3JpemF0aW9uIGNvZGUuIDotKQ=='
      },
      'grantee': {
        'type': 'BearerToken',
        'token': 'access-token-from-skill'
      }
    }

    # setup test devices
    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert msg['header']['name'] == 'AcceptGrant.Response'


async def test_report_lock_state(hass):
    """Test LockController implements lockState property."""
    hass.states.async_set(
        'lock.locked', STATE_LOCKED, {})
    hass.states.async_set(
        'lock.unlocked', STATE_UNLOCKED, {})
    hass.states.async_set(
        'lock.unknown', STATE_UNKNOWN, {})

    properties = await reported_properties(hass, 'lock.locked')
    properties.assert_equal('Alexa.LockController', 'lockState', 'LOCKED')

    properties = await reported_properties(hass, 'lock.unlocked')
    properties.assert_equal('Alexa.LockController', 'lockState', 'UNLOCKED')

    properties = await reported_properties(hass, 'lock.unknown')
    properties.assert_equal('Alexa.LockController', 'lockState', 'JAMMED')


async def test_report_dimmable_light_state(hass):
    """Test BrightnessController reports brightness correctly."""
    hass.states.async_set(
        'light.test_on', 'on', {'friendly_name': "Test light On",
                                'brightness': 128, 'supported_features': 1})
    hass.states.async_set(
        'light.test_off', 'off', {'friendly_name': "Test light Off",
                                  'supported_features': 1})

    properties = await reported_properties(hass, 'light.test_on')
    properties.assert_equal('Alexa.BrightnessController', 'brightness', 50)

    properties = await reported_properties(hass, 'light.test_off')
    properties.assert_equal('Alexa.BrightnessController', 'brightness', 0)


async def test_report_colored_light_state(hass):
    """Test ColorController reports color correctly."""
    hass.states.async_set(
        'light.test_on', 'on', {'friendly_name': "Test light On",
                                'hs_color': (180, 75),
                                'brightness': 128,
                                'supported_features': 17})
    hass.states.async_set(
        'light.test_off', 'off', {'friendly_name': "Test light Off",
                                  'supported_features': 17})

    properties = await reported_properties(hass, 'light.test_on')
    properties.assert_equal('Alexa.ColorController', 'color', {
        'hue': 180,
        'saturation': 0.75,
        'brightness': 128 / 255.0,
    })

    properties = await reported_properties(hass, 'light.test_off')
    properties.assert_equal('Alexa.ColorController', 'color', {
        'hue': 0,
        'saturation': 0,
        'brightness': 0,
    })


async def test_report_colored_temp_light_state(hass):
    """Test ColorTemperatureController reports color temp correctly."""
    hass.states.async_set(
        'light.test_on', 'on', {'friendly_name': "Test light On",
                                'color_temp': 240,
                                'supported_features': 2})
    hass.states.async_set(
        'light.test_off', 'off', {'friendly_name': "Test light Off",
                                  'supported_features': 2})

    properties = await reported_properties(hass, 'light.test_on')
    properties.assert_equal('Alexa.ColorTemperatureController',
                            'colorTemperatureInKelvin', 4166)

    properties = await reported_properties(hass, 'light.test_off')
    properties.assert_equal('Alexa.ColorTemperatureController',
                            'colorTemperatureInKelvin', 0)


async def reported_properties(hass, endpoint):
    """Use ReportState to get properties and return them.

    The result is a _ReportedProperties instance, which has methods to make
    assertions about the properties.
    """
    request = get_new_request('Alexa', 'ReportState', endpoint)
    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)
    await hass.async_block_till_done()
    return _ReportedProperties(msg['context']['properties'])


class _ReportedProperties:
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


async def test_entity_config(hass):
    """Test that we can configure things via entity config."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    hass.states.async_set(
        'light.test_1', 'on', {'friendly_name': "Test light 1"})

    config = smart_home.Config(
        endpoint=None,
        async_get_access_token=None,
        should_expose=lambda entity_id: True,
        entity_config={
            'light.test_1': {
                'name': 'Config name',
                'display_categories': 'SWITCH',
                'description': 'Config description'
            }
        }
    )

    msg = await smart_home.async_handle_message(
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


async def test_unsupported_domain(hass):
    """Discovery ignores entities of unknown domains."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    hass.states.async_set(
        'woz.boop', 'on', {'friendly_name': "Boop Woz"})

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request)

    assert 'event' in msg
    msg = msg['event']

    assert not msg['payload']['endpoints']


async def do_http_discovery(config, hass, hass_client):
    """Submit a request to the Smart Home HTTP API."""
    await async_setup_component(hass, alexa.DOMAIN, config)
    http_client = await hass_client()

    request = get_new_request('Alexa.Discovery', 'Discover')
    response = await http_client.post(
        smart_home.SMART_HOME_HTTP_ENDPOINT,
        data=json.dumps(request),
        headers={'content-type': 'application/json'})
    return response


async def test_http_api(hass, hass_client):
    """With `smart_home:` HTTP API is exposed."""
    config = {
        'alexa': {
            'smart_home': None
        }
    }

    response = await do_http_discovery(config, hass, hass_client)
    response_data = await response.json()

    # Here we're testing just the HTTP view glue -- details of discovery are
    # covered in other tests.
    assert response_data['event']['header']['name'] == 'Discover.Response'


async def test_http_api_disabled(hass, hass_client):
    """Without `smart_home:`, the HTTP API is disabled."""
    config = {
        'alexa': {}
    }
    response = await do_http_discovery(config, hass, hass_client)

    assert response.status == 404


@pytest.mark.parametrize(
    "domain,payload,source_list,idx", [
        ('media_player', 'GAME CONSOLE', ['tv', 'game console'], 1),
        ('media_player', 'SATELLITE TV', ['satellite-tv', 'game console'], 0),
        ('media_player', 'SATELLITE TV', ['satellite_tv', 'game console'], 0),
        ('media_player', 'BAD DEVICE', ['satellite_tv', 'game console'], None),
    ]
)
async def test_api_select_input(hass, domain, payload, source_list, idx):
    """Test api set input process."""
    hass.states.async_set(
        'media_player.test', 'off', {
            'friendly_name': "Test media player",
            'source': 'unknown',
            'source_list': source_list,
        })

    # test where no source matches
    if idx is None:
        await assert_request_fails(
            'Alexa.InputController', 'SelectInput', 'media_player#test',
            'media_player.select_source',
            hass,
            payload={'input': payload})
        return

    call, _ = await assert_request_calls_service(
        'Alexa.InputController', 'SelectInput', 'media_player#test',
        'media_player.select_source',
        hass,
        payload={'input': payload})
    assert call.data['source'] == source_list[idx]


async def test_logging_request(hass, events):
    """Test that we log requests."""
    context = Context()
    request = get_new_request('Alexa.Discovery', 'Discover')
    await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request, context)

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(events) == 1
    event = events[0]

    assert event.data['request'] == {
        'namespace': 'Alexa.Discovery',
        'name': 'Discover',
    }
    assert event.data['response'] == {
        'namespace': 'Alexa.Discovery',
        'name': 'Discover.Response'
    }
    assert event.context == context


async def test_logging_request_with_entity(hass, events):
    """Test that we log requests."""
    context = Context()
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#xy')
    await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request, context)

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(events) == 1
    event = events[0]

    assert event.data['request'] == {
        'namespace': 'Alexa.PowerController',
        'name': 'TurnOn',
        'entity_id': 'switch.xy'
    }
    # Entity doesn't exist
    assert event.data['response'] == {
        'namespace': 'Alexa',
        'name': 'ErrorResponse'
    }
    assert event.context == context


async def test_disabled(hass):
    """When enabled=False, everything fails."""
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#test')

    call_switch = async_mock_service(hass, 'switch', 'turn_on')

    msg = await smart_home.async_handle_message(
        hass, DEFAULT_CONFIG, request, enabled=False)
    await hass.async_block_till_done()

    assert 'event' in msg
    msg = msg['event']

    assert not call_switch
    assert msg['header']['name'] == 'ErrorResponse'
    assert msg['header']['namespace'] == 'Alexa'
    assert msg['payload']['type'] == 'BRIDGE_UNREACHABLE'


async def test_report_state(hass, aioclient_mock):
    """Test proactive state reports."""
    aioclient_mock.post(TEST_URL, json={'data': 'is irrelevant'})

    hass.states.async_set(
        'binary_sensor.test_contact',
        'on',
        {
            'friendly_name': "Test Contact Sensor",
            'device_class': 'door',
        }
    )

    await smart_home.async_enable_proactive_mode(hass, DEFAULT_CONFIG)

    hass.states.async_set(
        'binary_sensor.test_contact',
        'off',
        {
            'friendly_name': "Test Contact Sensor",
            'device_class': 'door',
        }
    )

    # To trigger event listener
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    call_json = json.loads(call[0][2])
    assert call_json["event"]["payload"]["change"]["properties"][0][
               "value"] == "NOT_DETECTED"
    assert call_json["event"]["endpoint"][
               "endpointId"] == "binary_sensor#test_contact"


async def run_auth_get_access_token(hass, aioclient_mock, expires_in,
                                    client_id, client_secret,
                                    accept_grant_code, refresh_token):
    """Do auth and request a new token for tests."""
    aioclient_mock.post(TEST_TOKEN_URL,
                        json={'access_token': 'the_access_token',
                              'refresh_token': refresh_token,
                              'expires_in': expires_in})

    auth = Auth(hass, client_id, client_secret)
    await auth.async_do_auth(accept_grant_code)
    await auth.async_get_access_token()


async def test_auth_get_access_token_expired(hass, aioclient_mock):
    """Test the auth get access token function."""
    client_id = "client123"
    client_secret = "shhhhh"
    accept_grant_code = "abcdefg"
    refresh_token = "refresher"

    await run_auth_get_access_token(hass, aioclient_mock, -5,
                                    client_id, client_secret,
                                    accept_grant_code, refresh_token)

    assert len(aioclient_mock.mock_calls) == 2
    calls = aioclient_mock.mock_calls

    auth_call_json = calls[0][2]
    token_call_json = calls[1][2]

    assert auth_call_json["grant_type"] == "authorization_code"
    assert auth_call_json["code"] == accept_grant_code
    assert auth_call_json["client_id"] == client_id
    assert auth_call_json["client_secret"] == client_secret

    assert token_call_json["grant_type"] == "refresh_token"
    assert token_call_json["refresh_token"] == refresh_token
    assert token_call_json["client_id"] == client_id
    assert token_call_json["client_secret"] == client_secret


async def test_auth_get_access_token_not_expired(hass, aioclient_mock):
    """Test the auth get access token function."""
    client_id = "client123"
    client_secret = "shhhhh"
    accept_grant_code = "abcdefg"
    refresh_token = "refresher"

    await run_auth_get_access_token(hass, aioclient_mock, 555,
                                    client_id, client_secret,
                                    accept_grant_code, refresh_token)

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    auth_call_json = call[0][2]

    assert auth_call_json["grant_type"] == "authorization_code"
    assert auth_call_json["code"] == accept_grant_code
    assert auth_call_json["client_id"] == client_id
    assert auth_call_json["client_secret"] == client_secret
