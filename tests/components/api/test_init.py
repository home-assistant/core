"""The tests for the Home Assistant API component."""
# pylint: disable=protected-access
import json
from unittest.mock import patch

from aiohttp import web
import pytest
import voluptuous as vol

from homeassistant import const
from homeassistant.bootstrap import DATA_LOGGING
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture
def mock_api_client(hass, hass_client):
    """Start the Home Assistant HTTP component and return admin API client."""
    hass.loop.run_until_complete(async_setup_component(hass, "api", {}))
    return hass.loop.run_until_complete(hass_client())


async def test_api_list_state_entities(hass, mock_api_client):
    """Test if the debug interface allows us to list state entities."""
    hass.states.async_set("test.entity", "hello")
    resp = await mock_api_client.get(const.URL_API_STATES)
    assert resp.status == 200
    json = await resp.json()

    remote_data = [ha.State.from_dict(item) for item in json]
    assert remote_data == hass.states.async_all()


async def test_api_get_state(hass, mock_api_client):
    """Test if the debug interface allows us to get a state."""
    hass.states.async_set("hello.world", "nice", {"attr": 1})
    resp = await mock_api_client.get(const.URL_API_STATES_ENTITY.format("hello.world"))
    assert resp.status == 200
    json = await resp.json()

    data = ha.State.from_dict(json)

    state = hass.states.get("hello.world")

    assert data.state == state.state
    assert data.last_changed == state.last_changed
    assert data.attributes == state.attributes


async def test_api_get_non_existing_state(hass, mock_api_client):
    """Test if the debug interface allows us to get a state."""
    resp = await mock_api_client.get(
        const.URL_API_STATES_ENTITY.format("does_not_exist")
    )
    assert resp.status == 404


async def test_api_state_change(hass, mock_api_client):
    """Test if we can change the state of an entity that exists."""
    hass.states.async_set("test.test", "not_to_be_set")

    await mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test.test"),
        json={"state": "debug_state_change2"},
    )

    assert hass.states.get("test.test").state == "debug_state_change2"


# pylint: disable=invalid-name
async def test_api_state_change_of_non_existing_entity(hass, mock_api_client):
    """Test if changing a state of a non existing entity is possible."""
    new_state = "debug_state_change"

    resp = await mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test_entity.that_does_not_exist"),
        json={"state": new_state},
    )

    assert resp.status == 201

    assert hass.states.get("test_entity.that_does_not_exist").state == new_state


# pylint: disable=invalid-name
async def test_api_state_change_with_bad_data(hass, mock_api_client):
    """Test if API sends appropriate error if we omit state."""
    resp = await mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test_entity.that_does_not_exist"), json={}
    )

    assert resp.status == 400


# pylint: disable=invalid-name
async def test_api_state_change_to_zero_value(hass, mock_api_client):
    """Test if changing a state to a zero value is possible."""
    resp = await mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test_entity.with_zero_state"),
        json={"state": 0},
    )

    assert resp.status == 201

    resp = await mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test_entity.with_zero_state"),
        json={"state": 0.0},
    )

    assert resp.status == 200


# pylint: disable=invalid-name
async def test_api_state_change_push(hass, mock_api_client):
    """Test if we can push a change the state of an entity."""
    hass.states.async_set("test.test", "not_to_be_set")

    events = []

    @ha.callback
    def event_listener(event):
        """Track events."""
        events.append(event)

    hass.bus.async_listen(const.EVENT_STATE_CHANGED, event_listener)

    await mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test.test"), json={"state": "not_to_be_set"}
    )
    await hass.async_block_till_done()
    assert len(events) == 0

    await mock_api_client.post(
        const.URL_API_STATES_ENTITY.format("test.test"),
        json={"state": "not_to_be_set", "force_update": True},
    )
    await hass.async_block_till_done()
    assert len(events) == 1


# pylint: disable=invalid-name
async def test_api_fire_event_with_no_data(hass, mock_api_client):
    """Test if the API allows us to fire an event."""
    test_value = []

    @ha.callback
    def listener(event):
        """Record that our event got called."""
        test_value.append(1)

    hass.bus.async_listen_once("test.event_no_data", listener)

    await mock_api_client.post(const.URL_API_EVENTS_EVENT.format("test.event_no_data"))
    await hass.async_block_till_done()

    assert len(test_value) == 1


# pylint: disable=invalid-name
async def test_api_fire_event_with_data(hass, mock_api_client):
    """Test if the API allows us to fire an event."""
    test_value = []

    @ha.callback
    def listener(event):
        """Record that our event got called.

        Also test if our data came through.
        """
        if "test" in event.data:
            test_value.append(1)

    hass.bus.async_listen_once("test_event_with_data", listener)

    await mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test_event_with_data"), json={"test": 1}
    )

    await hass.async_block_till_done()

    assert len(test_value) == 1


# pylint: disable=invalid-name
async def test_api_fire_event_with_invalid_json(hass, mock_api_client):
    """Test if the API allows us to fire an event."""
    test_value = []

    @ha.callback
    def listener(event):
        """Record that our event got called."""
        test_value.append(1)

    hass.bus.async_listen_once("test_event_bad_data", listener)

    resp = await mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test_event_bad_data"),
        data=json.dumps("not an object"),
    )

    await hass.async_block_till_done()

    assert resp.status == 400
    assert len(test_value) == 0

    # Try now with valid but unusable JSON
    resp = await mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test_event_bad_data"),
        data=json.dumps([1, 2, 3]),
    )

    await hass.async_block_till_done()

    assert resp.status == 400
    assert len(test_value) == 0


async def test_api_get_config(hass, mock_api_client):
    """Test the return of the configuration."""
    resp = await mock_api_client.get(const.URL_API_CONFIG)
    result = await resp.json()
    if "components" in result:
        result["components"] = set(result["components"])
    if "whitelist_external_dirs" in result:
        result["whitelist_external_dirs"] = set(result["whitelist_external_dirs"])

    assert hass.config.as_dict() == result


async def test_api_get_components(hass, mock_api_client):
    """Test the return of the components."""
    resp = await mock_api_client.get(const.URL_API_COMPONENTS)
    result = await resp.json()
    assert set(result) == hass.config.components


async def test_api_get_event_listeners(hass, mock_api_client):
    """Test if we can get the list of events being listened for."""
    resp = await mock_api_client.get(const.URL_API_EVENTS)
    data = await resp.json()

    local = hass.bus.async_listeners()

    for event in data:
        assert local.pop(event["event"]) == event["listener_count"]

    assert len(local) == 0


async def test_api_get_services(hass, mock_api_client):
    """Test if we can get a dict describing current services."""
    resp = await mock_api_client.get(const.URL_API_SERVICES)
    data = await resp.json()
    local_services = hass.services.async_services()

    for serv_domain in data:
        local = local_services.pop(serv_domain["domain"])

        assert serv_domain["services"] == local


async def test_api_call_service_no_data(hass, mock_api_client):
    """Test if the API allows us to call a service."""
    test_value = []

    @ha.callback
    def listener(service_call):
        """Record that our service got called."""
        test_value.append(1)

    hass.services.async_register("test_domain", "test_service", listener)

    await mock_api_client.post(
        const.URL_API_SERVICES_SERVICE.format("test_domain", "test_service")
    )
    await hass.async_block_till_done()
    assert len(test_value) == 1


async def test_api_call_service_with_data(hass, mock_api_client):
    """Test if the API allows us to call a service."""
    test_value = []

    @ha.callback
    def listener(service_call):
        """Record that our service got called.

        Also test if our data came through.
        """
        if "test" in service_call.data:
            test_value.append(1)

    hass.services.async_register("test_domain", "test_service", listener)

    await mock_api_client.post(
        const.URL_API_SERVICES_SERVICE.format("test_domain", "test_service"),
        json={"test": 1},
    )

    await hass.async_block_till_done()
    assert len(test_value) == 1


async def test_api_template(hass, mock_api_client):
    """Test the template API."""
    hass.states.async_set("sensor.temperature", 10)

    resp = await mock_api_client.post(
        const.URL_API_TEMPLATE,
        json={"template": "{{ states.sensor.temperature.state }}"},
    )

    body = await resp.text()

    assert body == "10"


async def test_api_template_error(hass, mock_api_client):
    """Test the template API."""
    hass.states.async_set("sensor.temperature", 10)

    resp = await mock_api_client.post(
        const.URL_API_TEMPLATE, json={"template": "{{ states.sensor.temperature.state"}
    )

    assert resp.status == 400


async def test_stream(hass, mock_api_client):
    """Test the stream."""
    listen_count = _listen_count(hass)

    resp = await mock_api_client.get(const.URL_API_STREAM)
    assert resp.status == 200
    assert listen_count + 1 == _listen_count(hass)

    hass.bus.async_fire("test_event")

    data = await _stream_next_event(resp.content)

    assert data["event_type"] == "test_event"


async def test_stream_with_restricted(hass, mock_api_client):
    """Test the stream with restrictions."""
    listen_count = _listen_count(hass)

    resp = await mock_api_client.get(
        "{}?restrict=test_event1,test_event3".format(const.URL_API_STREAM)
    )
    assert resp.status == 200
    assert listen_count + 1 == _listen_count(hass)

    hass.bus.async_fire("test_event1")
    data = await _stream_next_event(resp.content)
    assert data["event_type"] == "test_event1"

    hass.bus.async_fire("test_event2")
    hass.bus.async_fire("test_event3")
    data = await _stream_next_event(resp.content)
    assert data["event_type"] == "test_event3"


async def _stream_next_event(stream):
    """Read the stream for next event while ignoring ping."""
    while True:
        last_new_line = False
        data = b""

        while True:
            dat = await stream.read(1)
            if dat == b"\n" and last_new_line:
                break
            data += dat
            last_new_line = dat == b"\n"

        conv = data.decode("utf-8").strip()[6:]

        if conv != "ping":
            break
    return json.loads(conv)


def _listen_count(hass):
    """Return number of event listeners."""
    return sum(hass.bus.async_listeners().values())


async def test_api_error_log(hass, aiohttp_client, hass_access_token, hass_admin_user):
    """Test if we can fetch the error log."""
    hass.data[DATA_LOGGING] = "/some/path"
    await async_setup_component(hass, "api", {})
    client = await aiohttp_client(hass.http.app)

    resp = await client.get(const.URL_API_ERROR_LOG)
    # Verify auth required
    assert resp.status == 401

    with patch(
        "aiohttp.web.FileResponse", return_value=web.Response(status=200, text="Hello")
    ) as mock_file:
        resp = await client.get(
            const.URL_API_ERROR_LOG,
            headers={"Authorization": "Bearer {}".format(hass_access_token)},
        )

    assert len(mock_file.mock_calls) == 1
    assert mock_file.mock_calls[0][1][0] == hass.data[DATA_LOGGING]
    assert resp.status == 200
    assert await resp.text() == "Hello"

    # Verify we require admin user
    hass_admin_user.groups = []
    resp = await client.get(
        const.URL_API_ERROR_LOG,
        headers={"Authorization": "Bearer {}".format(hass_access_token)},
    )
    assert resp.status == 401


async def test_api_fire_event_context(hass, mock_api_client, hass_access_token):
    """Test if the API sets right context if we fire an event."""
    test_value = []

    @ha.callback
    def listener(event):
        """Record that our event got called."""
        test_value.append(event)

    hass.bus.async_listen("test.event", listener)

    await mock_api_client.post(
        const.URL_API_EVENTS_EVENT.format("test.event"),
        headers={"authorization": "Bearer {}".format(hass_access_token)},
    )
    await hass.async_block_till_done()

    refresh_token = await hass.auth.async_validate_access_token(hass_access_token)

    assert len(test_value) == 1
    assert test_value[0].context.user_id == refresh_token.user.id


async def test_api_call_service_context(hass, mock_api_client, hass_access_token):
    """Test if the API sets right context if we call a service."""
    calls = async_mock_service(hass, "test_domain", "test_service")

    await mock_api_client.post(
        "/api/services/test_domain/test_service",
        headers={"authorization": "Bearer {}".format(hass_access_token)},
    )
    await hass.async_block_till_done()

    refresh_token = await hass.auth.async_validate_access_token(hass_access_token)

    assert len(calls) == 1
    assert calls[0].context.user_id == refresh_token.user.id


async def test_api_set_state_context(hass, mock_api_client, hass_access_token):
    """Test if the API sets right context if we set state."""
    await mock_api_client.post(
        "/api/states/light.kitchen",
        json={"state": "on"},
        headers={"authorization": "Bearer {}".format(hass_access_token)},
    )

    refresh_token = await hass.auth.async_validate_access_token(hass_access_token)

    state = hass.states.get("light.kitchen")
    assert state.context.user_id == refresh_token.user.id


async def test_event_stream_requires_admin(hass, mock_api_client, hass_admin_user):
    """Test user needs to be admin to access event stream."""
    hass_admin_user.groups = []
    resp = await mock_api_client.get("/api/stream")
    assert resp.status == 401


async def test_states_view_filters(hass, mock_api_client, hass_admin_user):
    """Test filtering only visible states."""
    hass_admin_user.mock_policy({"entities": {"entity_ids": {"test.entity": True}}})
    hass.states.async_set("test.entity", "hello")
    hass.states.async_set("test.not_visible_entity", "invisible")
    resp = await mock_api_client.get(const.URL_API_STATES)
    assert resp.status == 200
    json = await resp.json()
    assert len(json) == 1
    assert json[0]["entity_id"] == "test.entity"


async def test_get_entity_state_read_perm(hass, mock_api_client, hass_admin_user):
    """Test getting a state requires read permission."""
    hass_admin_user.mock_policy({})
    resp = await mock_api_client.get("/api/states/light.test")
    assert resp.status == 401


async def test_post_entity_state_admin(hass, mock_api_client, hass_admin_user):
    """Test updating state requires admin."""
    hass_admin_user.groups = []
    resp = await mock_api_client.post("/api/states/light.test")
    assert resp.status == 401


async def test_delete_entity_state_admin(hass, mock_api_client, hass_admin_user):
    """Test deleting entity requires admin."""
    hass_admin_user.groups = []
    resp = await mock_api_client.delete("/api/states/light.test")
    assert resp.status == 401


async def test_post_event_admin(hass, mock_api_client, hass_admin_user):
    """Test sending event requires admin."""
    hass_admin_user.groups = []
    resp = await mock_api_client.post("/api/events/state_changed")
    assert resp.status == 401


async def test_rendering_template_admin(hass, mock_api_client, hass_admin_user):
    """Test rendering a template requires admin."""
    hass_admin_user.groups = []
    resp = await mock_api_client.post(const.URL_API_TEMPLATE)
    assert resp.status == 401


async def test_rendering_template_legacy_user(
    hass, mock_api_client, aiohttp_client, legacy_auth
):
    """Test rendering a template with legacy API password."""
    hass.states.async_set("sensor.temperature", 10)
    client = await aiohttp_client(hass.http.app)
    resp = await client.post(
        const.URL_API_TEMPLATE,
        json={"template": "{{ states.sensor.temperature.state }}"},
    )
    assert resp.status == 401


async def test_api_call_service_not_found(hass, mock_api_client):
    """Test if the API fails 400 if unknown service."""
    resp = await mock_api_client.post(
        const.URL_API_SERVICES_SERVICE.format("test_domain", "test_service")
    )
    assert resp.status == 400


async def test_api_call_service_bad_data(hass, mock_api_client):
    """Test if the API fails 400 if unknown service."""
    test_value = []

    @ha.callback
    def listener(service_call):
        """Record that our service got called."""
        test_value.append(1)

    hass.services.async_register(
        "test_domain", "test_service", listener, schema=vol.Schema({"hello": str})
    )

    resp = await mock_api_client.post(
        const.URL_API_SERVICES_SERVICE.format("test_domain", "test_service"),
        json={"hello": 5},
    )
    assert resp.status == 400
