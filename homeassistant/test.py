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
import homeassistant.components.httpinterface as hah

API_PASSWORD = "test1234"

HTTP_BASE_URL = "http://127.0.0.1:{}".format(hah.SERVER_PORT)


def _url(path=""):
    """ Helper method to generate urls. """
    return HTTP_BASE_URL + path


class HAHelper(object):  # pylint: disable=too-few-public-methods
    """ Helper class to keep track of current running HA instance. """
    core = None


def ensure_homeassistant_started():
    """ Ensures home assistant is started. """

    if not HAHelper.core:
        core = {'bus': ha.Bus()}
        core['statemachine'] = ha.StateMachine(core['bus'])

        core['bus'].listen_event('test_event', len)
        core['statemachine'].set_state('test', 'a_state')

        hah.HTTPInterface(core['bus'], core['statemachine'],
                          API_PASSWORD)

        core['bus'].fire_event(ha.EVENT_HOMEASSISTANT_START)

        # Give objects time to startup
        time.sleep(1)

        HAHelper.core = core

    return HAHelper.core['bus'], HAHelper.core['statemachine']


# pylint: disable=too-many-public-methods
class TestHTTPInterface(unittest.TestCase):
    """ Test the HTTP debug interface and API. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.bus, cls.statemachine = ensure_homeassistant_started()

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
            _url(hah.URL_API_STATES_ENTITY.format("test")))

        self.assertEqual(req.status_code, 401)

        req = requests.get(
            _url(hah.URL_API_STATES_ENTITY.format("test")),
            params={"api_password": "not the password"})

        self.assertEqual(req.status_code, 401)

    def test_debug_change_state(self):
        """ Test if we can change a state from the debug interface. """
        self.statemachine.set_state("test.test", "not_to_be_set_state")

        requests.post(_url(hah.URL_CHANGE_STATE),
                      data={"entity_id": "test.test",
                            "new_state": "debug_state_change2",
                            "api_password": API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test.test").state,
                         "debug_state_change2")

    def test_debug_fire_event(self):
        """ Test if we can fire an event from the debug interface. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify that our event got called and
                that test if our data came through. """
            if "test" in event.data:
                test_value.append(1)

        self.bus.listen_once_event("test_event_with_data", listener)

        requests.post(
            _url(hah.URL_FIRE_EVENT),
            data={"event_type": "test_event_with_data",
                  "event_data": '{"test": 1}',
                  "api_password": API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    def test_api_list_state_entities(self):
        """ Test if the debug interface allows us to list state entities. """
        req = requests.get(_url(hah.URL_API_STATES),
                           data={"api_password": API_PASSWORD})

        data = req.json()

        self.assertEqual(self.statemachine.entity_ids,
                         data['entity_ids'])

    def test_api_get_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(hah.URL_API_STATES_ENTITY.format("test")),
            data={"api_password": API_PASSWORD})

        data = ha.State.from_dict(req.json())

        state = self.statemachine.get_state("test")

        self.assertEqual(data.state, state.state)
        self.assertEqual(data.last_changed, state.last_changed)
        self.assertEqual(data.attributes, state.attributes)

    def test_api_get_non_existing_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(hah.URL_API_STATES_ENTITY.format("does_not_exist")),
            params={"api_password": API_PASSWORD})

        self.assertEqual(req.status_code, 422)

    def test_api_state_change(self):
        """ Test if we can change the state of an entity that exists. """

        self.statemachine.set_state("test.test", "not_to_be_set_state")

        requests.post(_url(hah.URL_API_STATES_ENTITY.format("test.test")),
                      data={"new_state": "debug_state_change2",
                            "api_password": API_PASSWORD})

        self.assertEqual(self.statemachine.get_state("test.test").state,
                         "debug_state_change2")

    # pylint: disable=invalid-name
    def test_api_state_change_of_non_existing_entity(self):
        """ Test if the API allows us to change a state of
            a non existing entity. """

        new_state = "debug_state_change"

        req = requests.post(
            _url(hah.URL_API_STATES_ENTITY.format(
                "test_entity_that_does_not_exist")),
            data={"new_state": new_state,
                  "api_password": API_PASSWORD})

        cur_state = (self.statemachine.
                     get_state("test_entity_that_does_not_exist").state)

        self.assertEqual(req.status_code, 201)
        self.assertEqual(cur_state, new_state)

    # pylint: disable=invalid-name
    def test_api_fire_event_with_no_data(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.bus.listen_once_event("test.event_no_data", listener)

        requests.post(
            _url(hah.URL_API_EVENTS_EVENT.format("test.event_no_data")),
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

        self.bus.listen_once_event("test_event_with_data", listener)

        requests.post(
            _url(hah.URL_API_EVENTS_EVENT.format("test_event_with_data")),
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

        self.bus.listen_once_event("test_event_with_bad_data", listener)

        req = requests.post(
            _url(hah.URL_API_EVENTS_EVENT.format("test_event")),
            data={"event_data": 'not json',
                  "api_password": API_PASSWORD})

        # It shouldn't but if it fires, allow the event to take place
        time.sleep(1)

        self.assertEqual(req.status_code, 422)
        self.assertEqual(len(test_value), 0)

    def test_api_get_event_listeners(self):
        """ Test if we can get the list of events being listened for. """
        req = requests.get(_url(hah.URL_API_EVENTS),
                           params={"api_password": API_PASSWORD})

        data = req.json()

        self.assertEqual(data['event_listeners'], self.bus.event_listeners)

    def test_api_get_services(self):
        """ Test if we can get a dict describing current services. """
        req = requests.get(_url(hah.URL_API_SERVICES),
                           params={"api_password": API_PASSWORD})

        data = req.json()

        self.assertEqual(data['services'], self.bus.services)

    def test_api_call_service_no_data(self):
        """ Test if the API allows us to call a service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify that our service got called. """
            test_value.append(1)

        self.bus.register_service("test_domain", "test_service", listener)

        requests.post(
            _url(hah.URL_API_SERVICES_SERVICE.format(
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

        self.bus.register_service("test_domain", "test_service", listener)

        requests.post(
            _url(hah.URL_API_SERVICES_SERVICE.format(
                "test_domain", "test_service")),
            data={"service_data": '{"test": 1}',
                  "api_password": API_PASSWORD})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)


class TestRemote(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.bus, cls.statemachine = ensure_homeassistant_started()

        cls.remote_sm = remote.StateMachine("127.0.0.1", API_PASSWORD)
        cls.remote_eb = remote.Bus("127.0.0.1", API_PASSWORD)
        cls.sm_with_remote_eb = ha.StateMachine(cls.remote_eb)
        cls.sm_with_remote_eb.set_state("test", "a_state")

    # pylint: disable=invalid-name
    def test_remote_sm_list_state_entities(self):
        """ Test if the debug interface allows us to list state entity ids. """

        self.assertEqual(self.statemachine.entity_ids,
                         self.remote_sm.entity_ids)

    def test_remote_sm_get_state(self):
        """ Test if debug interface allows us to get state of an entity. """
        remote_state = self.remote_sm.get_state("test")

        state = self.statemachine.get_state("test")

        self.assertEqual(remote_state.state, state.state)
        self.assertEqual(remote_state.last_changed, state.last_changed)
        self.assertEqual(remote_state.attributes, state.attributes)

    def test_remote_sm_get_non_existing_state(self):
        """ Test remote state machine to get state of non existing entity. """
        self.assertEqual(self.remote_sm.get_state("test_does_not_exist"), None)

    def test_remote_sm_state_change(self):
        """ Test if we can change the state of an existing entity. """

        self.remote_sm.set_state("test", "set_remotely", {"test": 1})

        state = self.statemachine.get_state("test")

        self.assertEqual(state.state, "set_remotely")
        self.assertEqual(state.attributes['test'], 1)

    def test_remote_eb_listening_for_same(self):
        """ Test if remote EB correctly reports listener overview. """
        self.assertEqual(self.bus.event_listeners,
                         self.remote_eb.event_listeners)

   # pylint: disable=invalid-name
    def test_remote_eb_fire_event_with_no_data(self):
        """ Test if the remote bus allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.bus.listen_once_event("test_event_no_data", listener)

        self.remote_eb.fire_event("test_event_no_data")

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    # pylint: disable=invalid-name
    def test_remote_eb_fire_event_with_data(self):
        """ Test if the remote bus allows us to fire an event. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            if event.data["test"] == 1:
                test_value.append(1)

        self.bus.listen_once_event("test_event_with_data", listener)

        self.remote_eb.fire_event("test_event_with_data", {"test": 1})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

   # pylint: disable=invalid-name
    def test_remote_eb_call_service_with_no_data(self):
        """ Test if the remote bus allows us to fire a service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify our service got called. """
            test_value.append(1)

        self.bus.register_service("test_domain", "test_service", listener)

        self.remote_eb.call_service("test_domain", "test_service")

        # Allow the service call to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    # pylint: disable=invalid-name
    def test_remote_eb_call_service_with_data(self):
        """ Test if the remote bus allows us to fire an event. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify our service got called. """
            if service_call.data["test"] == 1:
                test_value.append(1)

        self.bus.register_service("test_domain", "test_service", listener)

        self.remote_eb.call_service("test_domain", "test_service", {"test": 1})

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)

    def test_local_sm_with_remote_eb(self):
        """ Test if we get the event if we change a state on a
        StateMachine connected to a remote bus. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.bus.listen_once_event(ha.EVENT_STATE_CHANGED, listener)

        self.sm_with_remote_eb.set_state("test", "local sm with remote eb")

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(len(test_value), 1)
