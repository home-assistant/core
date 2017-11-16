"""The tests for the Google Assistant component."""
# pylint: disable=protected-access
import asyncio
import json

from aiohttp.hdrs import CONTENT_TYPE, AUTHORIZATION
import pytest
from tests.common import get_test_instance_port

from homeassistant import core, const, setup
from homeassistant.components import (
    fan, http, cover, light, switch, climate, async_setup, media_player)
from homeassistant.components import google_assistant as ga
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from . import DEMO_DEVICES

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
BASE_API_URL = "http://127.0.0.1:{}".format(SERVER_PORT)

HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

AUTHCFG = {
    'project_id': 'hasstest-1234',
    'client_id': 'helloworld',
    'access_token': 'superdoublesecret'
}
AUTH_HEADER = {AUTHORIZATION: 'Bearer {}'.format(AUTHCFG['access_token'])}


@pytest.fixture
def assistant_client(loop, hass_fixture, test_client):
    """Create web client for the Google Assistant API."""
    hass = hass_fixture
    web_app = hass.http.app

    ga.http.GoogleAssistantView(hass, AUTHCFG).register(web_app.router)
    ga.auth.GoogleAssistantAuthView(hass, AUTHCFG).register(web_app.router)

    return loop.run_until_complete(test_client(web_app))


@pytest.fixture
def hass_fixture(loop, hass):
    """Set up a HOme Assistant instance for these tests."""
    # We need to do this to get access to homeassistant/turn_(on,off)
    loop.run_until_complete(async_setup(hass, {core.DOMAIN: {}}))

    loop.run_until_complete(
        setup.async_setup_component(hass, http.DOMAIN, {
            http.DOMAIN: {
                http.CONF_SERVER_PORT: SERVER_PORT
            }
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, light.DOMAIN, {
            'light': [{
                'platform': 'demo'
            }]
        }))
    loop.run_until_complete(
        setup.async_setup_component(hass, switch.DOMAIN, {
            'switch': [{
                'platform': 'demo'
            }]
        }))
    loop.run_until_complete(
        setup.async_setup_component(hass, cover.DOMAIN, {
            'cover': [{
                'platform': 'demo'
            }],
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, media_player.DOMAIN, {
            'media_player': [{
                'platform': 'demo'
            }]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, fan.DOMAIN, {
            'fan': [{
                'platform': 'demo'
            }]
        }))

    loop.run_until_complete(
        setup.async_setup_component(hass, climate.DOMAIN, {
            'climate': [{
                'platform': 'demo'
            }]
        }))

    # Kitchen light is explicitly excluded from being exposed
    ceiling_lights_entity = hass.states.get('light.ceiling_lights')
    attrs = dict(ceiling_lights_entity.attributes)
    attrs[ga.const.ATTR_GOOGLE_ASSISTANT_NAME] = "Roof Lights"
    attrs[ga.const.CONF_ALIASES] = ['top lights', 'ceiling lights']
    hass.states.async_set(
        ceiling_lights_entity.entity_id,
        ceiling_lights_entity.state,
        attributes=attrs)

    # By setting the google_assistant_type = 'light'
    # we can override how a device is reported to GA
    switch_light = hass.states.get('switch.decorative_lights')
    attrs = dict(switch_light.attributes)
    attrs[ga.const.ATTR_GOOGLE_ASSISTANT_TYPE] = "light"
    hass.states.async_set(
        switch_light.entity_id,
        switch_light.state,
        attributes=attrs)

    return hass


@asyncio.coroutine
def test_auth(hass_fixture, assistant_client):
    """Test the auth process."""
    result = yield from assistant_client.get(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT + '/auth',
        params={
            'redirect_uri':
            'http://testurl/r/{}'.format(AUTHCFG['project_id']),
            'client_id': AUTHCFG['client_id'],
            'state': 'random1234',
        },
        allow_redirects=False)
    assert result.status == 301
    loc = result.headers.get('Location')
    assert AUTHCFG['access_token'] in loc


@asyncio.coroutine
def test_sync_request(hass_fixture, assistant_client):
    """Test a sync request."""
    reqid = '5711642932632160983'
    data = {'requestId': reqid, 'inputs': [{'intent': 'action.devices.SYNC'}]}
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=AUTH_HEADER)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert (
        sorted([dev['id'] for dev in devices])
        == sorted([dev['id'] for dev in DEMO_DEVICES]))

    for dev, demo in zip(
            sorted(devices, key=lambda d: d['id']),
            sorted(DEMO_DEVICES, key=lambda d: d['id'])):
        assert dev['name'] == demo['name']
        assert set(dev['traits']) == set(demo['traits'])
        assert dev['type'] == demo['type']
        if 'attributes' in demo:
            assert dev['attributes'] == demo['attributes']


@asyncio.coroutine
def test_query_request(hass_fixture, assistant_client):
    """Test a query request."""
    # hass.states.set("light.bedroom", "on")
    # hass.states.set("switch.outside", "off")
    # res = _sync_req()
    reqid = '5711642932632160984'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.QUERY',
            'payload': {
                'devices': [{
                    'id': "light.ceiling_lights",
                }, {
                    'id': "light.bed_light",
                }, {
                    'id': "light.kitchen_lights",
                }]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=AUTH_HEADER)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert len(devices) == 3
    assert devices['light.bed_light']['on'] is False
    assert devices['light.ceiling_lights']['on'] is True
    assert devices['light.ceiling_lights']['brightness'] == 70
    assert devices['light.kitchen_lights']['color']['spectrumRGB'] == 16727919
    assert devices['light.kitchen_lights']['color']['temperature'] == 4166


@asyncio.coroutine
def test_query_climate_request(hass_fixture, assistant_client):
    """Test a query request."""
    reqid = '5711642932632160984'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.QUERY',
            'payload': {
                'devices': [
                    {'id': 'climate.hvac'},
                    {'id': 'climate.heatpump'},
                    {'id': 'climate.ecobee'},
                ]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=AUTH_HEADER)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert devices == {
        'climate.heatpump': {
            'thermostatTemperatureSetpoint': 20.0,
            'thermostatTemperatureAmbient': 25.0,
            'thermostatMode': 'heat',
        },
        'climate.ecobee': {
            'thermostatTemperatureSetpointHigh': 24,
            'thermostatTemperatureAmbient': 23,
            'thermostatMode': 'on',
            'thermostatTemperatureSetpointLow': 21
        },
        'climate.hvac': {
            'thermostatTemperatureSetpoint': 21,
            'thermostatTemperatureAmbient': 22,
            'thermostatMode': 'cool',
            'thermostatHumidityAmbient': 54,
        }
    }


@asyncio.coroutine
def test_query_climate_request_f(hass_fixture, assistant_client):
    """Test a query request."""
    hass_fixture.config.units = IMPERIAL_SYSTEM
    reqid = '5711642932632160984'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.QUERY',
            'payload': {
                'devices': [
                    {'id': 'climate.hvac'},
                    {'id': 'climate.heatpump'},
                    {'id': 'climate.ecobee'},
                ]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=AUTH_HEADER)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    devices = body['payload']['devices']
    assert devices == {
        'climate.heatpump': {
            'thermostatTemperatureSetpoint': -6.7,
            'thermostatTemperatureAmbient': -3.9,
            'thermostatMode': 'heat',
        },
        'climate.ecobee': {
            'thermostatTemperatureSetpointHigh': -4.4,
            'thermostatTemperatureAmbient': -5,
            'thermostatMode': 'on',
            'thermostatTemperatureSetpointLow': -6.1,
        },
        'climate.hvac': {
            'thermostatTemperatureSetpoint': -6.1,
            'thermostatTemperatureAmbient': -5.6,
            'thermostatMode': 'cool',
            'thermostatHumidityAmbient': 54,
        }
    }


@asyncio.coroutine
def test_execute_request(hass_fixture, assistant_client):
    """Test a execute request."""
    # hass.states.set("light.bedroom", "on")
    # hass.states.set("switch.outside", "off")
    # res = _sync_req()
    reqid = '5711642932632160985'
    data = {
        'requestId':
        reqid,
        'inputs': [{
            'intent': 'action.devices.EXECUTE',
            'payload': {
                "commands": [{
                    "devices": [{
                        "id": "light.ceiling_lights",
                    }, {
                        "id": "switch.decorative_lights",
                    }, {
                        "id": "light.bed_light",
                    }],
                    "execution": [{
                        "command": "action.devices.commands.OnOff",
                        "params": {
                            "on": False
                        }
                    }]
                }, {
                    "devices": [{
                        "id": "light.kitchen_lights",
                    }],
                    "execution": [{
                        "command": "action.devices.commands.ColorAbsolute",
                        "params": {
                            "color": {
                                "spectrumRGB": 16711680,
                                "temperature": 2100
                            }
                        }
                    }]
                }, {
                    "devices": [{
                        "id": "light.kitchen_lights",
                    }],
                    "execution": [{
                        "command": "action.devices.commands.ColorAbsolute",
                        "params": {
                            "color": {
                                "spectrumRGB": 16711680
                            }
                        }
                    }]
                }]
            }
        }]
    }
    result = yield from assistant_client.post(
        ga.const.GOOGLE_ASSISTANT_API_ENDPOINT,
        data=json.dumps(data),
        headers=AUTH_HEADER)
    assert result.status == 200
    body = yield from result.json()
    assert body.get('requestId') == reqid
    commands = body['payload']['commands']
    assert len(commands) == 5
    ceiling = hass_fixture.states.get('light.ceiling_lights')
    assert ceiling.state == 'off'
    kitchen = hass_fixture.states.get('light.kitchen_lights')
    assert kitchen.attributes.get(light.ATTR_COLOR_TEMP) == 476
    assert kitchen.attributes.get(light.ATTR_RGB_COLOR) == (255, 0, 0)
    assert hass_fixture.states.get('switch.decorative_lights').state == 'off'
