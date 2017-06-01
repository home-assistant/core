"""The tests for the Home Assistant API component."""
# pylint: disable=protected-access
import asyncio
import json

import pytest

from homeassistant import const
import homeassistant.core as ha
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_api_client(hass, test_client):
    """Start the Hass HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, 'api', {}))
    return hass.loop.run_until_complete(test_client(hass.http.app))


@asyncio.coroutine
def test_api_list_state_entities(hass, mock_api_client):
    """Test if the debug interface allows us to list state entities."""
    hass.states.async_set('test.entity', 'hello')
    resp = yield from mock_api_client.get(const.URL_API_STATES)
    assert resp.status == 200
    json = yield from resp.json()

    remote_data = [ha.State.from_dict(item) for item in json]
    assert remote_data == hass.states.async_all()


@asyncio.coroutine
def test_api_get_state(hass, mock_api_client):
    """Test if the debug interface allows us to get a state."""
    hass.states.async_set('hello.world', 'nice', {
        'attr': 1,
    })
    resp = yield from mock_api_client.get(
        const.URL_API_STATES_ENTITY.format("hello.world"))
    assert resp.status == 200
    json = yield from resp.json()

    data = ha.State.from_dict(json)

    state = hass.states.get("hello.world")

    assert data.state == state.state
    assert data.last_changed == state.last_changed
    assert data.attributes == state.attributes


@asyncio.coroutine
def test_api_get_non_existing_state(hass, mock_api_client):
    """Test if the debug interface allows us to get a state."""
    resp = yield from mock_api_client.get(
        const.URL_API_STATES_ENTITY.format("does_not_exist"))
    assert resp.status == 404


@asyncio.coroutine
def test_api_state_change(hass, mock_api_client):
    """Test if we can change the state of an entity that exists."""
    hass.states.async_set("test.test", "not_to_be_set")

    yield from mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test.test"),
        json={"state": "debug_state_change2"})

    assert hass.states.get("test.test").state == "debug_state_change2"


# pylint: disable=invalid-name
@asyncio.coroutine
def test_api_state_change_of_non_existing_entity(hass, mock_api_client):
    """Test if changing a state of a non existing entity is possible."""
    new_state = "debug_state_change"

    resp = yield from mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test_entity.that_does_not_exist"),
        json={'state': new_state})

    assert resp.status == 201

    assert hass.states.get("test_entity.that_does_not_exist").state == \
        new_state


# pylint: disable=invalid-name
@asyncio.coroutine
def test_api_state_change_with_bad_data(hass, mock_api_client):
    """Test if API sends appropriate error if we omit state."""
    resp = yield from mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test_entity.that_does_not_exist"),
        json={})

    assert resp.status == 400


# pylint: disable=invalid-name
@asyncio.coroutine
def test_api_state_change_push(hass, mock_api_client):
    """Test if we can push a change the state of an entity."""
    hass.states.async_set("test.test", "not_to_be_set")

    events = []

    @ha.callback
    def event_listener(event):
        """Track events."""
        events.append(event)

    hass.bus.async_listen(const.EVENT_STATE_CHANGED, event_listener)

    yield from mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test.test"),
        json={"state": "not_to_be_set"})
    yield from hass.async_block_till_done()
    assert len(events) == 0

    yield from mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test.test"),
        json={"state": "not_to_be_set", "force_update": True})
    yield from hass.async_block_till_done()
    assert len(events) == 1


# pylint: disable=invalid-name
@asyncio.coroutine
def test_api_fire_event_with_no_data(hass, mock_api_client):
    """Test if the API allows us to fire an event."""
    test_value = []

    @ha.callback
    def listener(event):
        """Helper method that will verify our event got called."""
        test_value.append(1)

    hass.bus.async_listen_once("test.event_no_data", listener)

    yield from mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test.event_no_data"))
    yield from hass.async_block_till_done()

    assert len(test_value) == 1


# pylint: disable=invalid-name
@asyncio.coroutine
def test_api_fire_event_with_data(hass, mock_api_client):
    """Test if the API allows us to fire an event."""
    test_value = []

    @ha.callback
    def listener(event):
        """Helper method that will verify that our event got called.

        Also test if our data came through.
        """
        if "test" in event.data:
            test_value.append(1)

    hass.bus.async_listen_once("test_event_with_data", listener)

    yield from mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test_event_with_data"),
        json={"test": 1})

    yield from hass.async_block_till_done()

    assert len(test_value) == 1


# pylint: disable=invalid-name
@asyncio.coroutine
def test_api_fire_event_with_invalid_json(hass, mock_api_client):
    """Test if the API allows us to fire an event."""
    test_value = []

    @ha.callback
    def listener(event):
        """Helper method that will verify our event got called."""
        test_value.append(1)

    hass.bus.async_listen_once("test_event_bad_data", listener)

    resp = yield from mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test_event_bad_data"),
        data=json.dumps('not an object'))

    yield from hass.async_block_till_done()

    assert resp.status == 400
    assert len(test_value) == 0

    # Try now with valid but unusable JSON
    resp = yield from mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test_event_bad_data"),
        data=json.dumps([1, 2, 3]))

    yield from hass.async_block_till_done()

    assert resp.status == 400
    assert len(test_value) == 0


@asyncio.coroutine
def test_api_get_config(hass, mock_api_client):
    """Test the return of the configuration."""
    resp = yield from mock_api_client.get(const.URL_API_CONFIG)
    result = yield from resp.json()
    if 'components' in result:
        result['components'] = set(result['components'])

    assert hass.config.as_dict() == result


@asyncio.coroutine
def test_api_get_components(hass, mock_api_client):
    """Test the return of the components."""
    resp = yield from mock_api_client.get(const.URL_API_COMPONENTS)
    result = yield from resp.json()
    assert set(result) == hass.config.components


@asyncio.coroutine
def test_api_get_event_listeners(hass, mock_api_client):
    """Test if we can get the list of events being listened for."""
    resp = yield from mock_api_client.get(const.URL_API_EVENTS)
    data = yield from resp.json()

    local = hass.bus.async_listeners()

    for event in data:
        assert local.pop(event["event"]) == event["listener_count"]

    assert len(local) == 0


@asyncio.coroutine
def test_api_get_services(hass, mock_api_client):
    """Test if we can get a dict describing current services."""
    resp = yield from mock_api_client.get(const.URL_API_SERVICES)
    data = yield from resp.json()
    local_services = hass.services.async_services()

    for serv_domain in data:
        local = local_services.pop(serv_domain["domain"])

        assert serv_domain["services"] == local


@asyncio.coroutine
def test_api_call_service_no_data(hass, mock_api_client):
    """Test if the API allows us to call a service."""
    test_value = []

    @ha.callback
    def listener(service_call):
        """Helper method that will verify that our service got called."""
        test_value.append(1)

    hass.services.async_register("test_domain", "test_service", listener)

    yield from mock_api_client.post(
        const.URL_API_SERVICES_SERVICE.format(
            "test_domain", "test_service"))
    yield from hass.async_block_till_done()
    assert len(test_value) == 1


@asyncio.coroutine
def test_api_call_service_with_data(hass, mock_api_client):
    """Test if the API allows us to call a service."""
    test_value = []

    @ha.callback
    def listener(service_call):
        """Helper method that will verify that our service got called.

        Also test if our data came through.
        """
        if "test" in service_call.data:
            test_value.append(1)

    hass.services.async_register("test_domain", "test_service", listener)

    yield from mock_api_client.post(
        const.URL_API_SERVICES_SERVICE.format("test_domain", "test_service"),
        json={"test": 1})

    yield from hass.async_block_till_done()
    assert len(test_value) == 1


@asyncio.coroutine
def test_api_template(hass, mock_api_client):
    """Test the template API."""
    hass.states.async_set('sensor.temperature', 10)

    resp = yield from mock_api_client.post(
        const.URL_API_TEMPLATE,
        json={"template": '{{ states.sensor.temperature.state }}'})

    body = yield from resp.text()

    assert body == '10'


@asyncio.coroutine
def test_api_template_error(hass, mock_api_client):
    """Test the template API."""
    hass.states.async_set('sensor.temperature', 10)

    resp = yield from mock_api_client.post(
        const.URL_API_TEMPLATE,
        json={"template": '{{ states.sensor.temperature.state'})

    assert resp.status == 400


@asyncio.coroutine
def test_stream(hass, mock_api_client):
    """Test the stream."""
    listen_count = _listen_count(hass)

    resp = yield from mock_api_client.get(const.URL_API_STREAM)
    assert resp.status == 200
    assert listen_count + 1 == _listen_count(hass)

    hass.bus.async_fire('test_event')

    data = yield from _stream_next_event(resp.content)

    assert data['event_type'] == 'test_event'


@asyncio.coroutine
def test_stream_with_restricted(hass, mock_api_client):
    """Test the stream with restrictions."""
    listen_count = _listen_count(hass)

    resp = yield from mock_api_client.get(
        '{}?restrict=test_event1,test_event3'.format(const.URL_API_STREAM))
    assert resp.status == 200
    assert listen_count + 1 == _listen_count(hass)

    hass.bus.async_fire('test_event1')
    data = yield from _stream_next_event(resp.content)
    assert data['event_type'] == 'test_event1'

    hass.bus.async_fire('test_event2')
    hass.bus.async_fire('test_event3')
    data = yield from _stream_next_event(resp.content)
    assert data['event_type'] == 'test_event3'


@asyncio.coroutine
def _stream_next_event(stream):
    """Read the stream for next event while ignoring ping."""
    while True:
        last_new_line = False
        data = b''

        while True:
            dat = yield from stream.read(1)
            if dat == b'\n' and last_new_line:
                break
            data += dat
            last_new_line = dat == b'\n'

        conv = data.decode('utf-8').strip()[6:]

        if conv != 'ping':
            break
    return json.loads(conv)


def _listen_count(hass):
    """Return number of event listeners."""
    return sum(hass.bus.async_listeners().values())
