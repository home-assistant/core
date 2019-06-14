"""Test for smart home alexa support."""
import pytest

from homeassistant.core import Context, callback
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.components.alexa import (
    smart_home,
    messages,
)
from homeassistant.helpers import entityfilter

from tests.common import async_mock_service

from . import (
    get_new_request,
    MockConfig,
    DEFAULT_CONFIG,
    assert_request_calls_service,
    assert_request_fails,
    ReportedProperties,
    assert_power_controller_works,
    assert_scene_controller_works,
    reported_properties,
)


@pytest.fixture
def events(hass):
    """Fixture that catches alexa events."""
    events = []
    hass.bus.async_listen(
        smart_home.EVENT_ALEXA_SMART_HOME,
        callback(lambda e: events.append(e))
    )
    yield events


def test_create_api_message_defaults(hass):
    """Create a API message response of a request with defaults."""
    request = get_new_request('Alexa.PowerController', 'TurnOn', 'switch#xy')
    directive_header = request['directive']['header']
    directive = messages.AlexaDirective(request)

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
    directive = messages.AlexaDirective(request)

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


def get_capability(capabilities, capability_name):
    """Search a set of capabilities for a specific one."""
    for capability in capabilities:
        if capability['interface'] == capability_name:
            return capability

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
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )

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
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )

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
        'Alexa.EndpointHealth',
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
        'Alexa.EndpointHealth',
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
        'Alexa.SceneController',
    )
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
        'Alexa.SceneController',
    )
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
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )

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
        'Alexa.SceneController'
    )
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
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )


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
        'Alexa.EndpointHealth',
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
    assert_endpoint_capabilities(
        appliance,
        'Alexa.LockController',
        'Alexa.EndpointHealth',
    )

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
        'Alexa.EndpointHealth',
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


async def test_media_player_power(hass):
    """Test media player discovery with mapped on/off."""
    device = (
        'media_player.test',
        'off', {
            'friendly_name': "Test media player",
            'supported_features': 0xfa3f,
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
        'Alexa.Speaker',
        'Alexa.StepSpeaker',
        'Alexa.PlaybackController',
        'Alexa.EndpointHealth',
    )


async def test_alert(hass):
    """Test alert discovery."""
    device = ('alert.test', 'off', {'friendly_name': "Test alert"})
    appliance = await discovery_test(device, hass)

    assert appliance['endpointId'] == 'alert#test'
    assert appliance['displayCategories'][0] == "OTHER"
    assert appliance['friendlyName'] == "Test alert"
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )

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
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )

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
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )

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
        'Alexa.EndpointHealth',
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

    capabilities = assert_endpoint_capabilities(
        appliance,
        'Alexa.TemperatureSensor',
        'Alexa.EndpointHealth',
    )

    temp_sensor_capability = get_capability(capabilities,
                                            'Alexa.TemperatureSensor')
    assert temp_sensor_capability is not None
    properties = temp_sensor_capability['properties']
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

    capabilities = assert_endpoint_capabilities(
        appliance,
        'Alexa.ContactSensor',
        'Alexa.EndpointHealth',
    )

    contact_sensor_capability = get_capability(capabilities,
                                               'Alexa.ContactSensor')
    assert contact_sensor_capability is not None
    properties = contact_sensor_capability['properties']
    assert properties['retrievable'] is True
    assert {'name': 'detectionState'} in properties['supported']

    properties = await reported_properties(hass,
                                           'binary_sensor#test_contact')
    properties.assert_equal('Alexa.ContactSensor', 'detectionState',
                            'DETECTED')

    properties.assert_equal('Alexa.EndpointHealth', 'connectivity',
                            {'value': 'OK'})


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

    capabilities = assert_endpoint_capabilities(
        appliance,
        'Alexa.MotionSensor',
        'Alexa.EndpointHealth',
    )

    motion_sensor_capability = get_capability(capabilities,
                                              'Alexa.MotionSensor')
    assert motion_sensor_capability is not None
    properties = motion_sensor_capability['properties']
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
        'Alexa.EndpointHealth',
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
    properties = ReportedProperties(msg['context']['properties'])
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
    properties = ReportedProperties(msg['context']['properties'])
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
    properties = ReportedProperties(msg['context']['properties'])
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
    properties = ReportedProperties(msg['context']['properties'])
    properties.assert_equal(
        'Alexa.ThermostatController', 'thermostatMode', 'HEAT')

    call, msg = await assert_request_calls_service(
        'Alexa.ThermostatController', 'SetThermostatMode',
        'climate#test_thermostat', 'climate.set_operation_mode',
        hass,
        payload={'thermostatMode': {'value': 'COOL'}}
    )
    assert call.data['operation_mode'] == 'cool'
    properties = ReportedProperties(msg['context']['properties'])
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
    properties = ReportedProperties(msg['context']['properties'])
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

    alexa_config = MockConfig()
    alexa_config.should_expose = entityfilter.generate_filter(
        include_domains=[],
        include_entities=[],
        exclude_domains=['script'],
        exclude_entities=['cover.deny'],
    )

    msg = await smart_home.async_handle_message(hass, alexa_config, request)
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

    alexa_config = MockConfig()
    alexa_config.should_expose = entityfilter.generate_filter(
        include_domains=['automation', 'group'],
        include_entities=['script.deny'],
        exclude_domains=[],
        exclude_entities=[],
    )

    msg = await smart_home.async_handle_message(hass, alexa_config, request)
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

    alexa_config = MockConfig()
    alexa_config.should_expose = entityfilter.generate_filter(
        include_domains=['group'],
        include_entities=[],
        exclude_domains=[],
        exclude_entities=[],
    )

    msg = await smart_home.async_handle_message(hass, alexa_config, request)
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


async def test_entity_config(hass):
    """Test that we can configure things via entity config."""
    request = get_new_request('Alexa.Discovery', 'Discover')

    hass.states.async_set(
        'light.test_1', 'on', {'friendly_name': "Test light 1"})

    alexa_config = MockConfig()
    alexa_config.entity_config = {
        'light.test_1': {
            'name': 'Config name',
            'display_categories': 'SWITCH',
            'description': 'Config description'
        }
    }

    msg = await smart_home.async_handle_message(
        hass, alexa_config, request)

    assert 'event' in msg
    msg = msg['event']

    assert len(msg['payload']['endpoints']) == 1

    appliance = msg['payload']['endpoints'][0]
    assert appliance['endpointId'] == 'light#test_1'
    assert appliance['displayCategories'][0] == "SWITCH"
    assert appliance['friendlyName'] == "Config name"
    assert appliance['description'] == "Config description"
    assert_endpoint_capabilities(
        appliance,
        'Alexa.PowerController',
        'Alexa.EndpointHealth',
    )


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


async def test_endpoint_good_health(hass):
    """Test endpoint health reporting."""
    device = (
        'binary_sensor.test_contact',
        'on',
        {
            'friendly_name': "Test Contact Sensor",
            'device_class': 'door',
        }
    )
    await discovery_test(device, hass)
    properties = await reported_properties(hass, 'binary_sensor#test_contact')
    properties.assert_equal('Alexa.EndpointHealth', 'connectivity',
                            {'value': 'OK'})


async def test_endpoint_bad_health(hass):
    """Test endpoint health reporting."""
    device = (
        'binary_sensor.test_contact',
        'unavailable',
        {
            'friendly_name': "Test Contact Sensor",
            'device_class': 'door',
        }
    )
    await discovery_test(device, hass)
    properties = await reported_properties(hass, 'binary_sensor#test_contact')
    properties.assert_equal('Alexa.EndpointHealth', 'connectivity',
                            {'value': 'UNREACHABLE'})
