"""The tests for the Home Assistant API component."""
# pylint: disable=protected-access,too-many-public-methods
from contextlib import closing
import json
import tempfile
import time
import unittest
from unittest.mock import patch

import requests

from homeassistant import bootstrap, const
import homeassistant.core as ha
import homeassistant.components.http as http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

hass = None


def _url(path=""):
    """Helper method to generate URLs."""
    return HTTP_BASE_URL + path


def setUpModule():   # pylint: disable=invalid-name
    """Initialize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
         http.CONF_SERVER_PORT: SERVER_PORT}})

    bootstrap.setup_component(hass, 'api')

    hass.start()
    time.sleep(0.05)


def tearDownModule():   # pylint: disable=invalid-name
    """Stop the Home Assistant server."""
    hass.stop()


class TestAPI(unittest.TestCase):
    """Test the API."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_api_list_state_entities(self):
        """Test if the debug interface allows us to list state entities."""
        req = requests.get(_url(const.URL_API_STATES),
                           headers=HA_HEADERS)

        remote_data = [ha.State.from_dict(item) for item in req.json()]

        self.assertEqual(hass.states.all(), remote_data)

    def test_api_get_state(self):
        """Test if the debug interface allows us to get a state."""
        req = requests.get(
            _url(const.URL_API_STATES_ENTITY.format("test.test")),
            headers=HA_HEADERS)

        data = ha.State.from_dict(req.json())

        state = hass.states.get("test.test")

        self.assertEqual(state.state, data.state)
        self.assertEqual(state.last_changed, data.last_changed)
        self.assertEqual(state.attributes, data.attributes)

    def test_api_get_non_existing_state(self):
        """Test if the debug interface allows us to get a state."""
        req = requests.get(
            _url(const.URL_API_STATES_ENTITY.format("does_not_exist")),
            headers=HA_HEADERS)

        self.assertEqual(404, req.status_code)

    def test_api_state_change(self):
        """Test if we can change the state of an entity that exists."""
        hass.states.set("test.test", "not_to_be_set")

        requests.post(_url(const.URL_API_STATES_ENTITY.format("test.test")),
                      data=json.dumps({"state": "debug_state_change2"}),
                      headers=HA_HEADERS)

        self.assertEqual("debug_state_change2",
                         hass.states.get("test.test").state)

    # pylint: disable=invalid-name
    def test_api_state_change_of_non_existing_entity(self):
        """Test if changing a state of a non existing entity is possible."""
        new_state = "debug_state_change"

        req = requests.post(
            _url(const.URL_API_STATES_ENTITY.format(
                "test_entity.that_does_not_exist")),
            data=json.dumps({'state': new_state}),
            headers=HA_HEADERS)

        cur_state = (hass.states.
                     get("test_entity.that_does_not_exist").state)

        self.assertEqual(201, req.status_code)
        self.assertEqual(cur_state, new_state)

    # pylint: disable=invalid-name
    def test_api_state_change_with_bad_data(self):
        """Test if API sends appropriate error if we omit state."""
        req = requests.post(
            _url(const.URL_API_STATES_ENTITY.format(
                "test_entity.that_does_not_exist")),
            data=json.dumps({}),
            headers=HA_HEADERS)

        self.assertEqual(400, req.status_code)

    # pylint: disable=invalid-name
    def test_api_state_change_push(self):
        """Test if we can push a change the state of an entity."""
        hass.states.set("test.test", "not_to_be_set")

        events = []
        hass.bus.listen(const.EVENT_STATE_CHANGED, events.append)

        requests.post(_url(const.URL_API_STATES_ENTITY.format("test.test")),
                      data=json.dumps({"state": "not_to_be_set"}),
                      headers=HA_HEADERS)
        hass.bus._pool.block_till_done()
        self.assertEqual(0, len(events))

        requests.post(_url(const.URL_API_STATES_ENTITY.format("test.test")),
                      data=json.dumps({"state": "not_to_be_set",
                                       "force_update": True}),
                      headers=HA_HEADERS)
        hass.bus._pool.block_till_done()
        self.assertEqual(1, len(events))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_no_data(self):
        """Test if the API allows us to fire an event."""
        test_value = []

        def listener(event):
            """Helper method that will verify our event got called."""
            test_value.append(1)

        hass.bus.listen_once("test.event_no_data", listener)

        requests.post(
            _url(const.URL_API_EVENTS_EVENT.format("test.event_no_data")),
            headers=HA_HEADERS)

        hass.block_till_done()

        self.assertEqual(1, len(test_value))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_data(self):
        """Test if the API allows us to fire an event."""
        test_value = []

        def listener(event):
            """Helper method that will verify that our event got called.

            Also test if our data came through.
            """
            if "test" in event.data:
                test_value.append(1)

        hass.bus.listen_once("test_event_with_data", listener)

        requests.post(
            _url(const.URL_API_EVENTS_EVENT.format("test_event_with_data")),
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        hass.block_till_done()

        self.assertEqual(1, len(test_value))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_invalid_json(self):
        """Test if the API allows us to fire an event."""
        test_value = []

        def listener(event):
            """Helper method that will verify our event got called."""
            test_value.append(1)

        hass.bus.listen_once("test_event_bad_data", listener)

        req = requests.post(
            _url(const.URL_API_EVENTS_EVENT.format("test_event_bad_data")),
            data=json.dumps('not an object'),
            headers=HA_HEADERS)

        hass.block_till_done()

        self.assertEqual(400, req.status_code)
        self.assertEqual(0, len(test_value))

        # Try now with valid but unusable JSON
        req = requests.post(
            _url(const.URL_API_EVENTS_EVENT.format("test_event_bad_data")),
            data=json.dumps([1, 2, 3]),
            headers=HA_HEADERS)

        hass.block_till_done()

        self.assertEqual(400, req.status_code)
        self.assertEqual(0, len(test_value))

    def test_api_get_config(self):
        """Test the return of the configuration."""
        req = requests.get(_url(const.URL_API_CONFIG),
                           headers=HA_HEADERS)
        self.assertEqual(hass.config.as_dict(), req.json())

    def test_api_get_components(self):
        """Test the return of the components."""
        req = requests.get(_url(const.URL_API_COMPONENTS),
                           headers=HA_HEADERS)
        self.assertEqual(hass.config.components, req.json())

    def test_api_get_error_log(self):
        """Test the return of the error log."""
        test_content = 'Test String°'
        with tempfile.NamedTemporaryFile() as log:
            log.write(test_content.encode('utf-8'))
            log.flush()

            with patch.object(hass.config, 'path', return_value=log.name):
                req = requests.get(_url(const.URL_API_ERROR_LOG),
                                   headers=HA_HEADERS)
            self.assertEqual(test_content, req.text)
            self.assertIsNone(req.headers.get('expires'))

    def test_api_get_event_listeners(self):
        """Test if we can get the list of events being listened for."""
        req = requests.get(_url(const.URL_API_EVENTS),
                           headers=HA_HEADERS)

        local = hass.bus.listeners

        for event in req.json():
            self.assertEqual(event["listener_count"],
                             local.pop(event["event"]))

        self.assertEqual(0, len(local))

    def test_api_get_services(self):
        """Test if we can get a dict describing current services."""
        req = requests.get(_url(const.URL_API_SERVICES),
                           headers=HA_HEADERS)

        local_services = hass.services.services

        for serv_domain in req.json():
            local = local_services.pop(serv_domain["domain"])

            self.assertEqual(local, serv_domain["services"])

    def test_api_call_service_no_data(self):
        """Test if the API allows us to call a service."""
        test_value = []

        def listener(service_call):
            """Helper method that will verify that our service got called."""
            test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(const.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            headers=HA_HEADERS)

        hass.block_till_done()

        self.assertEqual(1, len(test_value))

    def test_api_call_service_with_data(self):
        """Test if the API allows us to call a service."""
        test_value = []

        def listener(service_call):
            """Helper method that will verify that our service got called.

            Also test if our data came through.
            """
            if "test" in service_call.data:
                test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(const.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        hass.block_till_done()

        self.assertEqual(1, len(test_value))

    def test_api_template(self):
        """Test the template API."""
        hass.states.set('sensor.temperature', 10)

        req = requests.post(
            _url(const.URL_API_TEMPLATE),
            json={"template": '{{ states.sensor.temperature.state }}'},
            headers=HA_HEADERS)

        self.assertEqual('10', req.text)

    def test_api_template_error(self):
        """Test the template API."""
        hass.states.set('sensor.temperature', 10)

        req = requests.post(
            _url(const.URL_API_TEMPLATE),
            data=json.dumps({"template":
                            '{{ states.sensor.temperature.state'}),
            headers=HA_HEADERS)

        self.assertEqual(400, req.status_code)

    def test_api_event_forward(self):
        """Test setting up event forwarding."""
        req = requests.post(
            _url(const.URL_API_EVENT_FORWARD),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.post(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({'host': '127.0.0.1'}),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.post(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({'api_password': 'bla-di-bla'}),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.post(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'api_password': 'bla-di-bla',
                'host': '127.0.0.1',
                'port': 'abcd'
                }),
            headers=HA_HEADERS)
        self.assertEqual(422, req.status_code)

        req = requests.post(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'api_password': 'bla-di-bla',
                'host': '127.0.0.1',
                'port': get_test_instance_port()
                }),
            headers=HA_HEADERS)
        self.assertEqual(422, req.status_code)

        # Setup a real one
        req = requests.post(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'api_password': API_PASSWORD,
                'host': '127.0.0.1',
                'port': SERVER_PORT
                }),
            headers=HA_HEADERS)
        self.assertEqual(200, req.status_code)

        # Delete it again..
        req = requests.delete(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({}),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.delete(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'host': '127.0.0.1',
                'port': 'abcd'
                }),
            headers=HA_HEADERS)
        self.assertEqual(422, req.status_code)

        req = requests.delete(
            _url(const.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'host': '127.0.0.1',
                'port': SERVER_PORT
                }),
            headers=HA_HEADERS)
        self.assertEqual(200, req.status_code)

    def test_stream(self):
        """Test the stream."""
        listen_count = self._listen_count()
        with closing(requests.get(_url(const.URL_API_STREAM), timeout=3,
                                  stream=True, headers=HA_HEADERS)) as req:
            stream = req.iter_content(1)
            self.assertEqual(listen_count + 1, self._listen_count())

            hass.bus.fire('test_event')

            data = self._stream_next_event(stream)

            self.assertEqual('test_event', data['event_type'])

    def test_stream_with_restricted(self):
        """Test the stream with restrictions."""
        listen_count = self._listen_count()
        url = _url('{}?restrict=test_event1,test_event3'.format(
            const.URL_API_STREAM))
        with closing(requests.get(url, stream=True, timeout=3,
                                  headers=HA_HEADERS)) as req:
            stream = req.iter_content(1)
            self.assertEqual(listen_count + 1, self._listen_count())

            hass.bus.fire('test_event1')
            data = self._stream_next_event(stream)
            self.assertEqual('test_event1', data['event_type'])

            hass.bus.fire('test_event2')
            hass.bus.fire('test_event3')

            data = self._stream_next_event(stream)
            self.assertEqual('test_event3', data['event_type'])

    def _stream_next_event(self, stream):
        """Read the stream for next event while ignoring ping."""
        while True:
            data = b''
            last_new_line = False
            for dat in stream:
                if dat == b'\n' and last_new_line:
                    break
                data += dat
                last_new_line = dat == b'\n'

            conv = data.decode('utf-8').strip()[6:]

            if conv != 'ping':
                break

        return json.loads(conv)

    def _listen_count(self):
        """Return number of event listeners."""
        return sum(hass.bus.listeners.values())
