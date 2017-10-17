"""The tests for the Google Actions component."""
# pylint: disable=protected-access
import json
import asyncio
import pytest

from homeassistant import setup, const, core
from homeassistant.components import (
    http, async_setup, light, cover, media_player, fan
)
from homeassistant.components import google_assistant as ga
from tests.common import get_test_instance_port

from . import DEMO_DEVICES


API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
BASE_API_URL = "http://127.0.0.1:{}".format(SERVER_PORT)

HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

AUTHCFG = {
    'project_id': 'hasstest-1234',
    'client_id': 'helloworld',
    'access_token': 'superdoublesecret'
}
AUTH_HEADER = {'Authorization': 'Bearer {}'.format(AUTHCFG['access_token'])}


@pytest.fixture
def assistant_client(loop, hass_fixture, test_client):
    """Create web client for emulated hue api."""
    hass = hass_fixture
    web_app = hass.http.app

    ga.http.GoogleAssistantView(hass, AUTHCFG).register(web_app.router)
    ga.auth.GoogleAssistantAuthView(hass, AUTHCFG).register(web_app.router)

    return loop.run_until_complete(test_client(web_app))


@pytest.fixture
def hass_fixture(loop, hass):
    """Setup a hass instance for these tests."""
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

    # Kitchen light is explicitly excluded from being exposed
    ceiling_lights_entity = hass.states.get('light.ceiling_lights')
    attrs = dict(ceiling_lights_entity.attributes)
    attrs[ga.const.ATTR_GOOGLE_ASSISTANT_NAME] = "Roof Lights"
    attrs[ga.const.CONF_ALIASES] = ['top lights', 'ceiling lights']
    hass.states.async_set(
        ceiling_lights_entity.entity_id,
        ceiling_lights_entity.state,
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
    # assert len(devices) == 4
    assert len(devices) == len(DEMO_DEVICES)
    # HACK this is kind of slow and lazy
    for dev in devices:
        for demo in DEMO_DEVICES:
            if dev['id'] == demo['id']:
                assert dev['name'] == demo['name']
                assert set(dev['traits']) == set(demo['traits'])
                assert dev['type'] == demo['type']


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
    assert len(devices) == 2
    assert devices['light.bed_light']['on'] is False
    assert devices['light.ceiling_lights']['on'] is True
    assert devices['light.ceiling_lights']['brightness'] == 70


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
                        "id": "light.bed_light",
                    }],
                    "execution": [{
                        "command": "action.devices.commands.OnOff",
                        "params": {
                            "on": False
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
    assert len(commands) == 2
    ceiling = hass_fixture.states.get('light.ceiling_lights')
    assert ceiling.state == 'off'
