"""Test the cloud.iot module."""
import contextlib
from unittest.mock import patch, MagicMock

from aiohttp import web
import jwt
import pytest

from homeassistant.core import State
from homeassistant.setup import async_setup_component
from homeassistant.components.cloud import (
    DOMAIN, ALEXA_SCHEMA, alexa_config)
from homeassistant.components.cloud.const import (
    PREF_ENABLE_ALEXA, PREF_ENABLE_GOOGLE)
from homeassistant.util.dt import utcnow
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from tests.components.alexa import test_smart_home as test_alexa
from tests.common import mock_coro, async_fire_time_changed

from . import mock_cloud_prefs, mock_cloud


@pytest.fixture
def mock_cloud_inst():
    """Mock cloud class."""
    return MagicMock(subscription_expired=False)


@pytest.fixture
async def mock_cloud_setup(hass):
    """Set up the cloud."""
    await mock_cloud(hass)


@pytest.fixture
def mock_cloud_login(hass, mock_cloud_setup):
    """Mock cloud is logged in."""
    hass.data[DOMAIN].id_token = jwt.encode({
        'email': 'hello@home-assistant.io',
        'custom:sub-exp': '2018-01-03',
        'cognito:username': 'abcdefghjkl',
    }, 'test')


async def test_handler_alexa(hass):
    """Test handler Alexa."""
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})
    hass.states.async_set(
        'switch.test2', 'on', {'friendly_name': "Test switch 2"})

    await mock_cloud(hass, {
        'alexa': {
            'filter': {
                'exclude_entities': 'switch.test2'
            },
            'entity_config': {
                'switch.test': {
                    'name': 'Config name',
                    'description': 'Config description',
                    'display_categories': 'LIGHT'
                }
            }
        }
    })

    mock_cloud_prefs(hass)
    cloud = hass.data['cloud']

    resp = await cloud.client.async_alexa_message(
        test_alexa.get_new_request('Alexa.Discovery', 'Discover'))

    endpoints = resp['event']['payload']['endpoints']

    assert len(endpoints) == 1
    device = endpoints[0]

    assert device['description'] == 'Config description'
    assert device['friendlyName'] == 'Config name'
    assert device['displayCategories'] == ['LIGHT']
    assert device['manufacturerName'] == 'Home Assistant'


async def test_handler_alexa_disabled(hass, mock_cloud_fixture):
    """Test handler Alexa when user has disabled it."""
    mock_cloud_fixture[PREF_ENABLE_ALEXA] = False
    cloud = hass.data['cloud']

    resp = await cloud.client.async_alexa_message(
        test_alexa.get_new_request('Alexa.Discovery', 'Discover'))

    assert resp['event']['header']['namespace'] == 'Alexa'
    assert resp['event']['header']['name'] == 'ErrorResponse'
    assert resp['event']['payload']['type'] == 'BRIDGE_UNREACHABLE'


async def test_handler_google_actions(hass):
    """Test handler Google Actions."""
    hass.states.async_set(
        'switch.test', 'on', {'friendly_name': "Test switch"})
    hass.states.async_set(
        'switch.test2', 'on', {'friendly_name': "Test switch 2"})
    hass.states.async_set(
        'group.all_locks', 'on', {'friendly_name': "Evil locks"})

    await mock_cloud(hass, {
        'google_actions': {
            'filter': {
                'exclude_entities': 'switch.test2'
            },
            'entity_config': {
                'switch.test': {
                    'name': 'Config name',
                    'aliases': 'Config alias',
                    'room': 'living room'
                }
            }
        }
    })

    mock_cloud_prefs(hass)
    cloud = hass.data['cloud']

    reqid = '5711642932632160983'
    data = {'requestId': reqid, 'inputs': [{'intent': 'action.devices.SYNC'}]}

    with patch(
        'hass_nabucasa.Cloud._decode_claims',
        return_value={'cognito:username': 'myUserName'}
    ):
        resp = await cloud.client.async_google_message(data)

    assert resp['requestId'] == reqid
    payload = resp['payload']

    assert payload['agentUserId'] == 'myUserName'

    devices = payload['devices']
    assert len(devices) == 1

    device = devices[0]
    assert device['id'] == 'switch.test'
    assert device['name']['name'] == 'Config name'
    assert device['name']['nicknames'] == ['Config alias']
    assert device['type'] == 'action.devices.types.SWITCH'
    assert device['roomHint'] == 'living room'


async def test_handler_google_actions_disabled(hass, mock_cloud_fixture):
    """Test handler Google Actions when user has disabled it."""
    mock_cloud_fixture[PREF_ENABLE_GOOGLE] = False

    with patch('hass_nabucasa.Cloud.start', return_value=mock_coro()):
        assert await async_setup_component(hass, 'cloud', {})

    reqid = '5711642932632160983'
    data = {'requestId': reqid, 'inputs': [{'intent': 'action.devices.SYNC'}]}

    cloud = hass.data['cloud']
    resp = await cloud.client.async_google_message(data)

    assert resp['requestId'] == reqid
    assert resp['payload']['errorCode'] == 'deviceTurnedOff'


async def test_webhook_msg(hass):
    """Test webhook msg."""
    with patch('hass_nabucasa.Cloud.start', return_value=mock_coro()):
        setup = await async_setup_component(hass, 'cloud', {
            'cloud': {}
        })
        assert setup
    cloud = hass.data['cloud']

    await cloud.client.prefs.async_initialize()
    await cloud.client.prefs.async_update(cloudhooks={
        'hello': {
            'webhook_id': 'mock-webhook-id',
            'cloudhook_id': 'mock-cloud-id'
        }
    })

    received = []

    async def handler(hass, webhook_id, request):
        """Handle a webhook."""
        received.append(request)
        return web.json_response({'from': 'handler'})

    hass.components.webhook.async_register(
        'test', 'Test', 'mock-webhook-id', handler)

    response = await cloud.client.async_webhook_message({
        'cloudhook_id': 'mock-cloud-id',
        'body': '{"hello": "world"}',
        'headers': {
            'content-type': 'application/json'
        },
        'method': 'POST',
        'query': None,
    })

    assert response == {
        'status': 200,
        'body': '{"from": "handler"}',
        'headers': {
            'Content-Type': 'application/json'
        }
    }

    assert len(received) == 1
    assert await received[0].json() == {
        'hello': 'world'
    }


async def test_google_config_expose_entity(
        hass, mock_cloud_setup, mock_cloud_login):
    """Test Google config exposing entity method uses latest config."""
    cloud_client = hass.data[DOMAIN].client
    state = State('light.kitchen', 'on')

    assert cloud_client.google_config.should_expose(state)

    await cloud_client.prefs.async_update_google_entity_config(
        entity_id='light.kitchen',
        should_expose=False,
    )

    assert not cloud_client.google_config.should_expose(state)


async def test_google_config_should_2fa(
        hass, mock_cloud_setup, mock_cloud_login):
    """Test Google config disabling 2FA method uses latest config."""
    cloud_client = hass.data[DOMAIN].client
    state = State('light.kitchen', 'on')

    assert cloud_client.google_config.should_2fa(state)

    await cloud_client.prefs.async_update_google_entity_config(
        entity_id='light.kitchen',
        disable_2fa=True,
    )

    assert not cloud_client.google_config.should_2fa(state)


async def test_alexa_config_expose_entity_prefs(hass, cloud_prefs):
    """Test Alexa config should expose using prefs."""
    entity_conf = {
        'should_expose': False
    }
    await cloud_prefs.async_update(alexa_entity_configs={
        'light.kitchen': entity_conf
    })
    conf = alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    assert not conf.should_expose('light.kitchen')
    entity_conf['should_expose'] = True
    assert conf.should_expose('light.kitchen')


async def test_alexa_config_report_state(hass, cloud_prefs):
    """Test Alexa config should expose using prefs."""
    conf = alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    assert cloud_prefs.alexa_report_state is False
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False

    with patch.object(conf, 'async_get_access_token',
                      return_value=mock_coro("hello")):
        await cloud_prefs.async_update(alexa_report_state=True)
        await hass.async_block_till_done()

    assert cloud_prefs.alexa_report_state is True
    assert conf.should_report_state is True
    assert conf.is_reporting_states is True

    await cloud_prefs.async_update(alexa_report_state=False)
    await hass.async_block_till_done()

    assert cloud_prefs.alexa_report_state is False
    assert conf.should_report_state is False
    assert conf.is_reporting_states is False


@contextlib.contextmanager
def patch_sync_helper():
    """Patch sync helper.

    In Py3.7 this would have been an async context manager.
    """
    to_update = []
    to_remove = []

    with patch(
            'homeassistant.components.cloud.alexa_config.SYNC_DELAY', 0
    ), patch(
        'homeassistant.components.cloud.alexa_config.AlexaConfig._sync_helper',
        side_effect=mock_coro
    ) as mock_helper:
        yield to_update, to_remove

    actual_to_update, actual_to_remove = mock_helper.mock_calls[0][1]
    to_update.extend(actual_to_update)
    to_remove.extend(actual_to_remove)


async def test_alexa_update_expose_trigger_sync(hass, cloud_prefs):
    """Test Alexa config responds to updating exposed entities."""
    alexa_config.AlexaConfig(hass, ALEXA_SCHEMA({}), cloud_prefs, None)

    with patch_sync_helper() as (to_update, to_remove):
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id='light.kitchen', should_expose=True
        )
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

    assert to_update == ['light.kitchen']
    assert to_remove == []

    with patch_sync_helper() as (to_update, to_remove):
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id='light.kitchen', should_expose=False
        )
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id='binary_sensor.door', should_expose=True
        )
        await cloud_prefs.async_update_alexa_entity_config(
            entity_id='sensor.temp', should_expose=True
        )
        await hass.async_block_till_done()
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

    assert sorted(to_update) == ['binary_sensor.door', 'sensor.temp']
    assert to_remove == ['light.kitchen']


async def test_alexa_entity_registry_sync(hass, mock_cloud_login, cloud_prefs):
    """Test Alexa config responds to entity registry."""
    alexa_config.AlexaConfig(
        hass, ALEXA_SCHEMA({}), cloud_prefs, hass.data['cloud'])

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(EVENT_ENTITY_REGISTRY_UPDATED, {
            'action': 'create',
            'entity_id': 'light.kitchen',
        })
        await hass.async_block_till_done()

    assert to_update == ['light.kitchen']
    assert to_remove == []

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(EVENT_ENTITY_REGISTRY_UPDATED, {
            'action': 'remove',
            'entity_id': 'light.kitchen',
        })
        await hass.async_block_till_done()

    assert to_update == []
    assert to_remove == ['light.kitchen']

    with patch_sync_helper() as (to_update, to_remove):
        hass.bus.async_fire(EVENT_ENTITY_REGISTRY_UPDATED, {
            'action': 'update',
            'entity_id': 'light.kitchen',
        })
        await hass.async_block_till_done()

    assert to_update == []
    assert to_remove == []
