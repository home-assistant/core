"""The tests for the emulated Hue component."""
import asyncio
import json
from unittest.mock import patch

from aiohttp.hdrs import CONTENT_TYPE
import pytest
from tests.common import get_test_instance_port

from homeassistant import core, const, setup
import homeassistant.components as core_components
from homeassistant.components import (
    fan, http, light, script, emulated_hue, media_player)
from homeassistant.components.emulated_hue import Config
from homeassistant.components.emulated_hue.hue_api import (
    HUE_API_STATE_ON, HUE_API_STATE_BRI, HueUsernameView, HueOneLightStateView,
    HueAllLightsStateView, HueOneLightChangeView)
from homeassistant.const import STATE_ON, STATE_OFF

HTTP_SERVER_PORT = get_test_instance_port()
BRIDGE_SERVER_PORT = get_test_instance_port()

BRIDGE_URL_BASE = 'http://127.0.0.1:{}'.format(BRIDGE_SERVER_PORT) + '{}'
JSON_HEADERS = {CONTENT_TYPE: const.CONTENT_TYPE_JSON}


@pytest.fixture
def hass_hue(loop, hass):
    """Setup a Home Assistant instance for these tests."""
    # We need to do this to get access to homeassistant/turn_(on,off)
    loop.run_until_complete(
        core_components.async_setup(hass, {core.DOMAIN: {}}))

    loop.run_until_complete(setup.async_setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}}))

    with patch('homeassistant.components'
               '.emulated_hue.UPNPResponderThread'):
        loop.run_until_complete(
            setup.async_setup_component(hass, emulated_hue.DOMAIN, {
                emulated_hue.DOMAIN: {
                    emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT,
                    emulated_hue.CONF_EXPOSE_BY_DEFAULT: True
                }
            }))

    loop.run_until_complete(
        setup.async_setup_component(hass, light.DOMAIN, {
            'light': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, script.DOMAIN, {
            'script': {
                'set_kitchen_light': {
                    'sequence': [
                        {
                            'service_template':
                                "light.turn_{{ requested_state }}",
                            'data_template': {
                                'entity_id': 'light.kitchen_lights',
                                'brightness': "{{ requested_level }}"
                                }
                        }
                    ]
                }
            }
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, media_player.DOMAIN, {
            'media_player': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, fan.DOMAIN, {
            'fan': [
                {
                    'platform': 'demo',
                }
            ]
        }))

    # Kitchen light is explicitly excluded from being exposed
    kitchen_light_entity = hass.states.get('light.kitchen_lights')
    attrs = dict(kitchen_light_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE] = False
    hass.states.async_set(
        kitchen_light_entity.entity_id, kitchen_light_entity.state,
        attributes=attrs)

    # Ceiling Fan is explicitly excluded from being exposed
    ceiling_fan_entity = hass.states.get('fan.ceiling_fan')
    attrs = dict(ceiling_fan_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE_HIDDEN] = True
    hass.states.async_set(
        ceiling_fan_entity.entity_id, ceiling_fan_entity.state,
        attributes=attrs)

    # Expose the script
    script_entity = hass.states.get('script.set_kitchen_light')
    attrs = dict(script_entity.attributes)
    attrs[emulated_hue.ATTR_EMULATED_HUE] = True
    hass.states.async_set(
        script_entity.entity_id, script_entity.state, attributes=attrs
    )

    return hass


@pytest.fixture
def hue_client(loop, hass_hue, test_client):
    """Create web client for emulated hue api."""
    web_app = hass_hue.http.app
    config = Config(None, {
        emulated_hue.CONF_TYPE: emulated_hue.TYPE_ALEXA,
        emulated_hue.CONF_ENTITIES: {
            'light.bed_light': {
                emulated_hue.CONF_ENTITY_HIDDEN: True
            }
        }
    })

    HueUsernameView().register(web_app.router)
    HueAllLightsStateView(config).register(web_app.router)
    HueOneLightStateView(config).register(web_app.router)
    HueOneLightChangeView(config).register(web_app.router)

    return loop.run_until_complete(test_client(web_app))


@asyncio.coroutine
def test_discover_lights(hue_client):
    """Test the discovery of lights."""
    result = yield from hue_client.get('/api/username/lights')

    assert result.status == 200
    assert 'application/json' in result.headers['content-type']

    result_json = yield from result.json()

    devices = set(val['uniqueid'] for val in result_json.values())

    # Make sure the lights we added to the config are there
    assert 'light.ceiling_lights' in devices
    assert 'light.bed_light' not in devices
    assert 'script.set_kitchen_light' in devices
    assert 'light.kitchen_lights' not in devices
    assert 'media_player.living_room' in devices
    assert 'media_player.bedroom' in devices
    assert 'media_player.walkman' in devices
    assert 'media_player.lounge_room' in devices
    assert 'fan.living_room_fan' in devices
    assert 'fan.ceiling_fan' not in devices


@asyncio.coroutine
def test_get_light_state(hass_hue, hue_client):
    """Test the getting of light state."""
    # Turn office light on and set to 127 brightness
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_ON,
        {
            const.ATTR_ENTITY_ID: 'light.ceiling_lights',
            light.ATTR_BRIGHTNESS: 127
        },
        blocking=True)

    office_json = yield from perform_get_light_state(
        hue_client, 'light.ceiling_lights', 200)

    assert office_json['state'][HUE_API_STATE_ON] is True
    assert office_json['state'][HUE_API_STATE_BRI] == 127

    # Check all lights view
    result = yield from hue_client.get('/api/username/lights')

    assert result.status == 200
    assert 'application/json' in result.headers['content-type']

    result_json = yield from result.json()

    assert 'light.ceiling_lights' in result_json
    assert result_json['light.ceiling_lights']['state'][HUE_API_STATE_BRI] == \
        127

    # Turn office light off
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_OFF,
        {
            const.ATTR_ENTITY_ID: 'light.ceiling_lights'
        },
        blocking=True)

    office_json = yield from perform_get_light_state(
        hue_client, 'light.ceiling_lights', 200)

    assert office_json['state'][HUE_API_STATE_ON] is False
    assert office_json['state'][HUE_API_STATE_BRI] == 0

    # Make sure bedroom light isn't accessible
    yield from perform_get_light_state(
        hue_client, 'light.bed_light', 404)

    # Make sure kitchen light isn't accessible
    yield from perform_get_light_state(
        hue_client, 'light.kitchen_lights', 404)


@asyncio.coroutine
def test_put_light_state(hass_hue, hue_client):
    """Test the setting of light states."""
    yield from perform_put_test_on_ceiling_lights(hass_hue, hue_client)

    # Turn the bedroom light on first
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_ON,
        {const.ATTR_ENTITY_ID: 'light.ceiling_lights',
         light.ATTR_BRIGHTNESS: 153},
        blocking=True)

    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 153

    # Go through the API to turn it off
    ceiling_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.ceiling_lights', False)

    ceiling_result_json = yield from ceiling_result.json()

    assert ceiling_result.status == 200
    assert 'application/json' in ceiling_result.headers['content-type']

    assert len(ceiling_result_json) == 1

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_OFF

    # Make sure we can't change the bedroom light state
    bedroom_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.bed_light', True)
    assert bedroom_result.status == 404

    # Make sure we can't change the kitchen light state
    kitchen_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.kitchen_light', True)
    assert kitchen_result.status == 404


@asyncio.coroutine
def test_put_light_state_script(hass_hue, hue_client):
    """Test the setting of script variables."""
    # Turn the kitchen light off first
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'light.kitchen_lights'},
        blocking=True)

    # Emulated hue converts 0-100% to 0-255.
    level = 23
    brightness = round(level * 255 / 100)

    script_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'script.set_kitchen_light', True, brightness)

    script_result_json = yield from script_result.json()

    assert script_result.status == 200
    assert len(script_result_json) == 2

    kitchen_light = hass_hue.states.get('light.kitchen_lights')
    assert kitchen_light.state == 'on'
    assert kitchen_light.attributes[light.ATTR_BRIGHTNESS] == level


@asyncio.coroutine
def test_put_light_state_media_player(hass_hue, hue_client):
    """Test turning on media player and setting volume."""
    # Turn the music player off first
    yield from hass_hue.services.async_call(
        media_player.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'media_player.walkman'},
        blocking=True)

    # Emulated hue converts 0.0-1.0 to 0-255.
    level = 0.25
    brightness = round(level * 255)

    mp_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'media_player.walkman', True, brightness)

    mp_result_json = yield from mp_result.json()

    assert mp_result.status == 200
    assert len(mp_result_json) == 2

    walkman = hass_hue.states.get('media_player.walkman')
    assert walkman.state == 'playing'
    assert walkman.attributes[media_player.ATTR_MEDIA_VOLUME_LEVEL] == level


@asyncio.coroutine
def test_put_light_state_fan(hass_hue, hue_client):
    """Test turning on fan and setting speed."""
    # Turn the fan off first
    yield from hass_hue.services.async_call(
        fan.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'fan.living_room_fan'},
        blocking=True)

    # Emulated hue converts 0-100% to 0-255.
    level = 43
    brightness = round(level * 255 / 100)

    fan_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'fan.living_room_fan', True, brightness)

    fan_result_json = yield from fan_result.json()

    assert fan_result.status == 200
    assert len(fan_result_json) == 2

    living_room_fan = hass_hue.states.get('fan.living_room_fan')
    assert living_room_fan.state == 'on'
    assert living_room_fan.attributes[fan.ATTR_SPEED] == fan.SPEED_MEDIUM


# pylint: disable=invalid-name
@asyncio.coroutine
def test_put_with_form_urlencoded_content_type(hass_hue, hue_client):
    """Test the form with urlencoded content."""
    # Needed for Alexa
    yield from perform_put_test_on_ceiling_lights(
        hass_hue, hue_client, 'application/x-www-form-urlencoded')

    # Make sure we fail gracefully when we can't parse the data
    data = {'key1': 'value1', 'key2': 'value2'}
    result = yield from hue_client.put(
        '/api/username/lights/light.ceiling_lights/state',
        headers={
            'content-type': 'application/x-www-form-urlencoded'
        },
        data=data,
    )

    assert result.status == 400


@asyncio.coroutine
def test_entity_not_found(hue_client):
    """Test for entity which are not found."""
    result = yield from hue_client.get(
        '/api/username/lights/not.existant_entity')

    assert result.status == 404

    result = yield from hue_client.put(
        '/api/username/lights/not.existant_entity/state')

    assert result.status == 404


@asyncio.coroutine
def test_allowed_methods(hue_client):
    """Test the allowed methods."""
    result = yield from hue_client.get(
        '/api/username/lights/light.ceiling_lights/state')

    assert result.status == 405

    result = yield from hue_client.put(
        '/api/username/lights/light.ceiling_lights')

    assert result.status == 405

    result = yield from hue_client.put(
        '/api/username/lights')

    assert result.status == 405


@asyncio.coroutine
def test_proper_put_state_request(hue_client):
    """Test the request to set the state."""
    # Test proper on value parsing
    result = yield from hue_client.put(
            '/api/username/lights/{}/state'.format(
                'light.ceiling_lights'),
            data=json.dumps({HUE_API_STATE_ON: 1234}))

    assert result.status == 400

    # Test proper brightness value parsing
    result = yield from hue_client.put(
        '/api/username/lights/{}/state'.format(
            'light.ceiling_lights'),
        data=json.dumps({
            HUE_API_STATE_ON: True,
            HUE_API_STATE_BRI: 'Hello world!'
        }))

    assert result.status == 400


# pylint: disable=invalid-name
def perform_put_test_on_ceiling_lights(hass_hue, hue_client,
                                       content_type='application/json'):
    """Test the setting of a light."""
    # Turn the office light off first
    yield from hass_hue.services.async_call(
        light.DOMAIN, const.SERVICE_TURN_OFF,
        {const.ATTR_ENTITY_ID: 'light.ceiling_lights'},
        blocking=True)

    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_OFF

    # Go through the API to turn it on
    office_result = yield from perform_put_light_state(
        hass_hue, hue_client,
        'light.ceiling_lights', True, 56, content_type)

    assert office_result.status == 200
    assert 'application/json' in office_result.headers['content-type']

    office_result_json = yield from office_result.json()

    assert len(office_result_json) == 2

    # Check to make sure the state changed
    ceiling_lights = hass_hue.states.get('light.ceiling_lights')
    assert ceiling_lights.state == STATE_ON
    assert ceiling_lights.attributes[light.ATTR_BRIGHTNESS] == 56


@asyncio.coroutine
def perform_get_light_state(client, entity_id, expected_status):
    """Test the getting of a light state."""
    result = yield from client.get('/api/username/lights/{}'.format(entity_id))

    assert result.status == expected_status

    if expected_status == 200:
        assert 'application/json' in result.headers['content-type']

        return (yield from result.json())

    return None


@asyncio.coroutine
def perform_put_light_state(hass_hue, client, entity_id, is_on,
                            brightness=None, content_type='application/json'):
    """Test the setting of a light state."""
    req_headers = {'Content-Type': content_type}

    data = {HUE_API_STATE_ON: is_on}

    if brightness is not None:
        data[HUE_API_STATE_BRI] = brightness

    result = yield from client.put(
        '/api/username/lights/{}/state'.format(entity_id), headers=req_headers,
        data=json.dumps(data).encode())

    # Wait until state change is complete before continuing
    yield from hass_hue.async_block_till_done()

    return result
