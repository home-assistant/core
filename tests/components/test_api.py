"""
tests.test_component_http
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Home Assistant HTTP component does what it should do.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
import json

import requests

import homeassistant.core as ha
import homeassistant.bootstrap as bootstrap
import homeassistant.remote as remote
import homeassistant.components.http as http
from homeassistant.const import HTTP_HEADER_HA_AUTH

API_PASSWORD = "test1234"

# Somehow the socket that holds the default port does not get released
# when we close down HA in a different test case. Until I have figured
# out what is going on, let's run this test on a different port.
SERVER_PORT = 8120

HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)

HA_HEADERS = {HTTP_HEADER_HA_AUTH: API_PASSWORD}

hass = None


def _url(path=""):
    """ Helper method to generate urls. """
    return HTTP_BASE_URL + path


def setUpModule():   # pylint: disable=invalid-name
    """ Initalizes a Home Assistant server. """
    global hass

    hass = ha.HomeAssistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
         http.CONF_SERVER_PORT: SERVER_PORT}})

    bootstrap.setup_component(hass, 'api')

    hass.start()


def tearDownModule():   # pylint: disable=invalid-name
    """ Stops the Home Assistant server. """
    hass.stop()


class TestAPI(unittest.TestCase):
    """ Test the API. """

    # TODO move back to http component and test with use_auth.
    def test_access_denied_without_password(self):
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")))

        self.assertEqual(401, req.status_code)

    def test_access_denied_with_wrong_password(self):
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")),
            headers={HTTP_HEADER_HA_AUTH: 'wrongpassword'})

        self.assertEqual(401, req.status_code)

    def test_api_list_state_entities(self):
        """ Test if the debug interface allows us to list state entities. """
        req = requests.get(_url(remote.URL_API_STATES),
                           headers=HA_HEADERS)

        remote_data = [ha.State.from_dict(item) for item in req.json()]

        self.assertEqual(hass.states.all(), remote_data)

    def test_api_get_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test.test")),
            headers=HA_HEADERS)

        data = ha.State.from_dict(req.json())

        state = hass.states.get("test.test")

        self.assertEqual(state.state, data.state)
        self.assertEqual(state.last_changed, data.last_changed)
        self.assertEqual(state.attributes, data.attributes)

    def test_api_get_non_existing_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("does_not_exist")),
            headers=HA_HEADERS)

        self.assertEqual(404, req.status_code)

    def test_api_state_change(self):
        """ Test if we can change the state of an entity that exists. """

        hass.states.set("test.test", "not_to_be_set")

        requests.post(_url(remote.URL_API_STATES_ENTITY.format("test.test")),
                      data=json.dumps({"state": "debug_state_change2"}),
                      headers=HA_HEADERS)

        self.assertEqual("debug_state_change2",
                         hass.states.get("test.test").state)

    # pylint: disable=invalid-name
    def test_api_state_change_of_non_existing_entity(self):
        """ Test if the API allows us to change a state of
            a non existing entity. """

        new_state = "debug_state_change"

        req = requests.post(
            _url(remote.URL_API_STATES_ENTITY.format(
                "test_entity.that_does_not_exist")),
            data=json.dumps({'state': new_state}),
            headers=HA_HEADERS)

        cur_state = (hass.states.
                     get("test_entity.that_does_not_exist").state)

        self.assertEqual(201, req.status_code)
        self.assertEqual(cur_state, new_state)

    # pylint: disable=invalid-name
    def test_api_state_change_with_bad_data(self):
        """ Test if API sends appropriate error if we omit state. """

        req = requests.post(
            _url(remote.URL_API_STATES_ENTITY.format(
                "test_entity.that_does_not_exist")),
            data=json.dumps({}),
            headers=HA_HEADERS)

        self.assertEqual(400, req.status_code)

    # pylint: disable=invalid-name
    def test_api_fire_event_with_no_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        hass.bus.listen_once("test.event_no_data", listener)

        requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test.event_no_data")),
            headers=HA_HEADERS)

        hass.pool.block_till_done()

        self.assertEqual(1, len(test_value))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        hass.bus.listen_once("test_event_with_data", listener)

        requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event_with_data")),
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        hass.pool.block_till_done()

        self.assertEqual(1, len(test_value))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_invalid_json(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        hass.bus.listen_once("test_event_bad_data", listener)

        req = requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event_bad_data")),
            data=json.dumps('not an object'),
            headers=HA_HEADERS)

        hass.pool.block_till_done()

        self.assertEqual(422, req.status_code)
        self.assertEqual(0, len(test_value))

        # Try now with valid but unusable JSON
        req = requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event_bad_data")),
            data=json.dumps([1, 2, 3]),
            headers=HA_HEADERS)

        hass.pool.block_till_done()

        self.assertEqual(422, req.status_code)
        self.assertEqual(0, len(test_value))

    def test_api_get_event_listeners(self):
        """ Test if we can get the list of events being listened for. """
        req = requests.get(_url(remote.URL_API_EVENTS),
                           headers=HA_HEADERS)

        local = hass.bus.listeners

        for event in req.json():
            self.assertEqual(event["listener_count"],
                             local.pop(event["event"]))

        self.assertEqual(0, len(local))

    def test_api_get_services(self):
        """ Test if we can get a dict describing current services. """
        req = requests.get(_url(remote.URL_API_SERVICES),
                           headers=HA_HEADERS)

        local_services = hass.services.services

        for serv_domain in req.json():
            local = local_services.pop(serv_domain["domain"])

            self.assertEqual(local, serv_domain["services"])

    def test_api_call_service_no_data(self):
        """ Test if the API allows us to call a service. """
        test_value = []

        def listener(service_call):
            """ Helper method that will verify that our service got called. """
            test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(remote.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            headers=HA_HEADERS)

        hass.pool.block_till_done()

        self.assertEqual(1, len(test_value))

    def test_api_call_service_with_data(self):
        """ Test if the API allows us to call a service. """
        test_value = []

        def listener(service_call):
            """ Helper method that will verify that our service got called and
                that test if our data came through. """
            if "test" in service_call.data:
                test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(remote.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        hass.pool.block_till_done()

        self.assertEqual(1, len(test_value))

    def test_api_event_forward(self):
        """ Test setting up event forwarding. """

        req = requests.post(
            _url(remote.URL_API_EVENT_FORWARD),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.post(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({'host': '127.0.0.1'}),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.post(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({'api_password': 'bla-di-bla'}),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.post(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'api_password': 'bla-di-bla',
                'host': '127.0.0.1',
                'port': 'abcd'
                }),
            headers=HA_HEADERS)
        self.assertEqual(422, req.status_code)

        req = requests.post(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'api_password': 'bla-di-bla',
                'host': '127.0.0.1',
                'port': '8125'
                }),
            headers=HA_HEADERS)
        self.assertEqual(422, req.status_code)

        # Setup a real one
        req = requests.post(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'api_password': API_PASSWORD,
                'host': '127.0.0.1',
                'port': SERVER_PORT
                }),
            headers=HA_HEADERS)
        self.assertEqual(200, req.status_code)

        # Delete it again..
        req = requests.delete(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({}),
            headers=HA_HEADERS)
        self.assertEqual(400, req.status_code)

        req = requests.delete(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'host': '127.0.0.1',
                'port': 'abcd'
                }),
            headers=HA_HEADERS)
        self.assertEqual(422, req.status_code)

        req = requests.delete(
            _url(remote.URL_API_EVENT_FORWARD),
            data=json.dumps({
                'host': '127.0.0.1',
                'port': SERVER_PORT
                }),
            headers=HA_HEADERS)
        self.assertEqual(200, req.status_code)
