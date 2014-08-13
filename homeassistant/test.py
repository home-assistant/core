"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""

import unittest
import time

import requests

import homeassistant as ha
import homeassistant.remote as remote
import homeassistant.components.http as http

API_PASSWORD = "test1234"

HTTP_BASE_URL = "http://127.0.0.1:{}".format(remote.SERVER_PORT)


def _url(path=""):
    """ Helper method to generate urls. """
    return HTTP_BASE_URL + path


class HAHelper(object):  # pylint: disable=too-few-public-methods
    """ Helper class to keep track of current running HA instance. """
    hass = None
    slave = None


def ensure_homeassistant_started():
    """ Ensures home assistant is started. """

    if not HAHelper.hass:
        hass = ha.HomeAssistant()

        hass.bus.listen('test_event', len)
        hass.states.set('test', 'a_state')

        http.setup(hass,
                   {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD}})

        hass.start()

        # Give objects time to startup
        time.sleep(1)

        HAHelper.hass = hass

    return HAHelper.hass


def ensure_slave_started():
    """ Ensure a home assistant slave is started. """

    ensure_homeassistant_started()

    if not HAHelper.slave:
        local_api = remote.API("127.0.0.1", API_PASSWORD, 8124)
        remote_api = remote.API("127.0.0.1", API_PASSWORD)
        slave = remote.HomeAssistant(remote_api, local_api)

        http.setup(slave,
                   {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                                  http.CONF_SERVER_PORT: 8124}})

        slave.start()

        # Give objects time to startup
        time.sleep(1)

        HAHelper.slave = slave

    return HAHelper.slave


# pylint: disable=too-many-public-methods
class TestHTTP(unittest.TestCase):
    """ Test the HTTP debug interface and API. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()

    def test_debug_interface(self):
        """ Test if we can login by comparing not logged in screen to
            logged in screen. """

        with_pw = requests.get(
            _url("/?api_password={}".format(API_PASSWORD)))

        without_pw = requests.get(_url())

        self.assertNotEqual(without_pw.text, with_pw.text)

    def test_api_password(self):
        """ Test if we get access denied if we omit or provide
            a wrong api password. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")))

        self.assertEqual(req.status_code, 401)

        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")),
            params={"api_password": "not the password"})

        self.assertEqual(req.status_code, 401)

    def test_debug_change_state(self):
        """ Test if we can change a state from the debug interface. """
        self.hass.states.set("test.test", "not_to_be_set")

        requests.post(_url(http.URL_CHANGE_STATE),
                      data={"entity_id": "test.test",
                            "new_state": "debug_state_change2",
                            "api_password": API_PASSWORD})

        self.assertEqual(self.hass.states.get("test.test").state,
                         "debug_state_change2")

    def test_debug_fire_event(self):
        """ Test if we can fire an event from the debug interface. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        self.hass.listen_once_event("test_event_with_data", listener)

        requests.post(
            _url(http.URL_FIRE_EVENT),
            data={"event_type": "test_event_with_data",
                  "event_data": '{"test": 1}',
                  "api_password": API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    def test_api_list_state_entities(self):
        """ Test if the debug interface allows us to list state entities. """
        req = requests.get(_url(remote.URL_API_STATES),
                           data={"api_password": API_PASSWORD})

        remote_data = req.json()

        local_data = {entity_id: state.as_dict() for entity_id, state
                      in self.hass.states.all().items()}

        self.assertEqual(local_data, remote_data)

    def test_api_get(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")),
            data={"api_password": API_PASSWORD})

        data = ha.State.from_dict(req.json())

        state = self.hass.states.get("test")

        self.assertEqual(data.state, state.state)
        self.assertEqual(data.last_changed, state.last_changed)
        self.assertEqual(data.attributes, state.attributes)

    def test_api_get_non_existing_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("does_not_exist")),
            params={"api_password": API_PASSWORD})

        self.assertEqual(req.status_code, 422)

    def test_api_state_change(self):
        """ Test if we can change the state of an entity that exists. """

        self.hass.states.set("test.test", "not_to_be_set")

        requests.post(_url(remote.URL_API_STATES_ENTITY.format("test.test")),
                      data={"new_state": "debug_state_change2",
                            "api_password": API_PASSWORD})

        self.assertEqual(self.hass.states.get("test.test").state,
                         "debug_state_change2")

    # pylint: disable=invalid-name
    def test_api_state_change_of_non_existing_entity(self):
        """ Test if the API allows us to change a state of
            a non existing entity. """

        new_state = "debug_state_change"

        req = requests.post(
            _url(remote.URL_API_STATES_ENTITY.format(
                "test_entity_that_does_not_exist")),
            data={"new_state": new_state,
                  "api_password": API_PASSWORD})

        cur_state = (self.hass.states.
                     get("test_entity_that_does_not_exist").state)

        self.assertEqual(req.status_code, 201)
        self.assertEqual(cur_state, new_state)

    # pylint: disable=invalid-name
    def test_api_fire_event_with_no_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.hass.listen_once_event("test.event_no_data", listener)

        requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test.event_no_data")),
            data={"api_password": API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    # pylint: disable=invalid-name
    def test_api_fire_event_with_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        self.hass.listen_once_event("test_event_with_data", listener)

        requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event_with_data")),
            data={"event_data": '{"test": 1}',
                  "api_password": API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    # pylint: disable=invalid-name
    def test_api_fire_event_with_invalid_json(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):    # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.hass.listen_once_event("test_event_with_bad_data", listener)

        req = requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event")),
            data={"event_data": 'not json',
                  "api_password": API_PASSWORD})

        # It shouldn't but if it fires, allow the event to take place
        time.sleep(1)

        self.assertEqual(req.status_code, 422)
        self.assertEqual(len(test_value), 0)

    def test_api_get_event_listeners(self):
        """ Test if we can get the list of events being listened for. """
        req = requests.get(_url(remote.URL_API_EVENTS),
                           params={"api_password": API_PASSWORD})

        data = req.json()

        self.assertEqual(data['event_listeners'], self.hass.bus.listeners)

    def test_api_get_services(self):
        """ Test if we can get a dict describing current services. """
        req = requests.get(_url(remote.URL_API_SERVICES),
                           params={"api_password": API_PASSWORD})

        data = req.json()

        self.assertEqual(data['services'], self.hass.services.services)

    def test_api_call_service_no_data(self):
        """ Test if the API allows us to call a service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify that our service got called. """
            test_value.append(1)

        self.hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(remote.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            data={"api_password": API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    def test_api_call_service_with_data(self):
        """ Test if the API allows us to call a service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify that our service got called and
                that test if our data came through. """
            if "test" in service_call.data:
                test_value.append(1)

        self.hass.services.register("test_domain", "test_service", listener)

        requests.post(
            _url(remote.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            data={"service_data": '{"test": 1}',
                  "api_password": API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)


class TestRemoteMethods(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()

        cls.api = remote.API("127.0.0.1", API_PASSWORD)

    def test_get_event_listeners(self):
        """ Test Python API get_event_listeners. """

        self.assertEqual(
            remote.get_event_listeners(self.api), self.hass.bus.listeners)

    def test_fire_event(self):
        """ Test Python API fire_event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.hass.listen_once_event("test.event_no_data", listener)

        remote.fire_event(self.api, "test.event_no_data")

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    def test_get_state(self):
        """ Test Python API get_state. """

        self.assertEqual(
            remote.get_state(self.api, 'test'), self.hass.states.get('test'))

    def test_get_states(self):
        """ Test Python API get_state_entity_ids. """

        self.assertEqual(
            remote.get_states(self.api), self.hass.states.all())

    def test_set_state(self):
        """ Test Python API set_state. """
        remote.set_state(self.api, 'test', 'set_test')

        self.assertEqual(self.hass.states.get('test').state, 'set_test')

    def test_is_state(self):
        """ Test Python API is_state. """

        self.assertEqual(
            remote.is_state(self.api, 'test',
                            self.hass.states.get('test').state),
            True)

    def test_get_services(self):
        """ Test Python API get_services. """

        self.assertEqual(
            remote.get_services(self.api), self.hass.services.services)

    def test_call_service(self):
        """ Test Python API call_service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify that our service got called. """
            test_value.append(1)

        self.hass.services.register("test_domain", "test_service", listener)

        remote.call_service(self.api, "test_domain", "test_service")

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)


class TestRemoteClasses(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()
        cls.slave = ensure_slave_started()

    def test_statemachine_init(self):
        """ Tests if remote.StateMachine copies all states on init. """
        self.assertEqual(self.hass.states.all(), self.slave.states.all())

    def test_statemachine_set(self):
        """ Tests if setting the state on a slave is recorded. """
        self.slave.states.set("test", "remote.statemachine test")

        # Allow interaction between 2 instances
        time.sleep(1)

        self.assertEqual(self.slave.states.get("test").state,
                         "remote.statemachine test")

    def test_eventbus_fire(self):
        """ Test if events fired from the eventbus get fired. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.slave.listen_once_event("test.event_no_data", listener)

        self.slave.bus.fire("test.event_no_data")

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)
