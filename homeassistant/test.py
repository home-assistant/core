"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""
import os
import unittest
import time
import json

import requests

import homeassistant as ha
import homeassistant.remote as remote
import homeassistant.components.http as http

API_PASSWORD = "test1234"

HTTP_BASE_URL = "http://127.0.0.1:{}".format(remote.SERVER_PORT)

HA_HEADERS = {remote.AUTH_HEADER: API_PASSWORD}


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

        hass.bus.listen('test_event', lambda _: _)
        hass.states.set('test.test', 'a_state')

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
class TestHomeAssistant(unittest.TestCase):
    """
    Tests the Home Assistant core classes.
    Currently only includes tests to test cases that do not
    get tested in the API integration tests.
    """

    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.hass = ha.HomeAssistant()
        self.hass.states.set("light.Bowl", "on")
        self.hass.states.set("switch.AC", "off")

    def test_get_config_path(self):
        """ Test get_config_path method. """
        self.assertEqual(os.getcwd(), self.hass.config_dir)

        self.assertEqual(os.path.join(os.getcwd(), "test.conf"),
                         self.hass.get_config_path("test.conf"))

    def test_block_till_stoped(self):
        """ Test if we can block till stop service is called. """
        pass

    def test_get_entity_ids(self):
        """ Test get_entity_ids method. """
        ent_ids = self.hass.get_entity_ids()
        self.assertEqual(2, len(ent_ids))
        self.assertTrue('light.Bowl' in ent_ids)
        self.assertTrue('switch.AC' in ent_ids)

        ent_ids = self.hass.get_entity_ids('light')
        self.assertEqual(1, len(ent_ids))
        self.assertTrue('light.Bowl' in ent_ids)

    def test_track_state_change(self):
        """ Test track_state_change. """
        # with with from_state, to_state and without
        pass

    def test_track_point_in_time(self):
        """ Test track point in time. """
        pass

    def test_track_time_change(self):
        """ Test tracking time change. """
        # with paramters
        # without parameters
        pass


# pylint: disable=too-many-public-methods
class TestEventBus(unittest.TestCase):
    """ Test EventBus methods. """

    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.bus = ha.EventBus()
        self.bus.listen('test_event', lambda x: len)

    def test_add_remove_listener(self):
        """ Test remove_listener method. """
        old_count = len(self.bus.listeners)

        listener = lambda x: len

        self.bus.listen('test', listener)

        self.assertEqual(old_count + 1, len(self.bus.listeners))

        self.bus.remove_listener('test', listener)

        self.assertEqual(old_count, len(self.bus.listeners))


# pylint: disable=too-many-public-methods
class TestState(unittest.TestCase):
    """ Test EventBus methods. """

    def test_init(self):
        """ Test state.init """
        self.assertRaises(
            ha.InvalidEntityFormatError, ha.State,
            'invalid_entity_format', 'test_state')


# pylint: disable=too-many-public-methods
class TestStateMachine(unittest.TestCase):
    """ Test EventBus methods. """

    def setUp(self):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        self.bus = ha.EventBus()
        self.states = ha.StateMachine(self.bus)
        self.states.set("light.Bowl", "on")
        self.states.set("switch.AC", "off")

    def test_is_state(self):
        """ Test is_state method. """
        self.assertTrue(self.states.is_state('light.Bowl', 'on'))
        self.assertFalse(self.states.is_state('light.Bowl', 'off'))
        self.assertFalse(self.states.is_state('light.Non_existing', 'on'))

    def test_remove(self):
        """ Test remove method. """
        self.assertTrue('light.Bowl' in self.states.entity_ids)
        self.assertTrue(self.states.remove('light.Bowl'))
        self.assertFalse('light.Bowl' in self.states.entity_ids)

        # If it does not exist, we should get False
        self.assertFalse(self.states.remove('light.Bowl'))


# pylint: disable=too-many-public-methods
class TestServiceRegistry(unittest.TestCase):
    """ Test EventBus methods. """

    def setUp(self):     # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        pool = ha.create_worker_pool()
        self.bus = ha.EventBus(pool)
        self.services = ha.ServiceRegistry(self.bus, pool)
        self.services.register("test_domain", "test_service", lambda x: len)

    def test_has_service(self):
        """ Test has_service method. """
        self.assertTrue(
            self.services.has_service("test_domain", "test_service"))


# pylint: disable=too-many-public-methods
class TestHTTP(unittest.TestCase):
    """ Test the HTTP debug interface and API. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()

    def test_api_password(self):
        """ Test if we get access denied if we omit or provide
            a wrong api password. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")))

        self.assertEqual(401, req.status_code)

        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test")),
            headers={remote.AUTH_HEADER: 'wrongpassword'})

        self.assertEqual(401, req.status_code)

    def test_api_list_state_entities(self):
        """ Test if the debug interface allows us to list state entities. """
        req = requests.get(_url(remote.URL_API_STATES),
                           headers=HA_HEADERS)

        remote_data = [ha.State.from_dict(item) for item in req.json()]

        self.assertEqual(self.hass.states.all(), remote_data)

    def test_api_get_state(self):
        """ Test if the debug interface allows us to get a state. """
        req = requests.get(
            _url(remote.URL_API_STATES_ENTITY.format("test.test")),
            headers=HA_HEADERS)

        data = ha.State.from_dict(req.json())

        state = self.hass.states.get("test.test")

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

        self.hass.states.set("test.test", "not_to_be_set")

        requests.post(_url(remote.URL_API_STATES_ENTITY.format("test.test")),
                      data=json.dumps({"state": "debug_state_change2",
                                       "api_password": API_PASSWORD}))

        self.assertEqual("debug_state_change2",
                         self.hass.states.get("test.test").state)

    # pylint: disable=invalid-name
    def test_api_state_change_of_non_existing_entity(self):
        """ Test if the API allows us to change a state of
            a non existing entity. """

        new_state = "debug_state_change"

        req = requests.post(
            _url(remote.URL_API_STATES_ENTITY.format(
                "test_entity.that_does_not_exist")),
            data=json.dumps({"state": new_state,
                             "api_password": API_PASSWORD}))

        cur_state = (self.hass.states.
                     get("test_entity.that_does_not_exist").state)

        self.assertEqual(201, req.status_code)
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
            headers=HA_HEADERS)

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(1, len(test_value))

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
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(1, len(test_value))

    # pylint: disable=invalid-name
    def test_api_fire_event_with_invalid_json(self):
        """ Test if the API allows us to fire an event. """
        test_value = []

        def listener(event):    # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        self.hass.listen_once_event("test_event_bad_data", listener)

        req = requests.post(
            _url(remote.URL_API_EVENTS_EVENT.format("test_event_bad_data")),
            data=json.dumps('not an object'),
            headers=HA_HEADERS)

        # It shouldn't but if it fires, allow the event to take place
        time.sleep(1)

        self.assertEqual(422, req.status_code)
        self.assertEqual(0, len(test_value))

    def test_api_get_event_listeners(self):
        """ Test if we can get the list of events being listened for. """
        req = requests.get(_url(remote.URL_API_EVENTS),
                           headers=HA_HEADERS)

        local = self.hass.bus.listeners

        for event in req.json():
            self.assertEqual(event["listener_count"],
                             local.pop(event["event"]))

        self.assertEqual(0, len(local))

    def test_api_get_services(self):
        """ Test if we can get a dict describing current services. """
        req = requests.get(_url(remote.URL_API_SERVICES),
                           headers=HA_HEADERS)

        local_services = self.hass.services.services

        for serv_domain in req.json():
            local = local_services.pop(serv_domain["domain"])

            self.assertEqual(local, serv_domain["services"])

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
            headers=HA_HEADERS)

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(1, len(test_value))

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
            data=json.dumps({"test": 1}),
            headers=HA_HEADERS)

        # Allow the event to take place
        time.sleep(1)

        self.assertEqual(1, len(test_value))


class TestRemoteMethods(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()

        cls.api = remote.API("127.0.0.1", API_PASSWORD)

    def test_get_event_listeners(self):
        """ Test Python API get_event_listeners. """
        local_data = self.hass.bus.listeners
        remote_data = remote.get_event_listeners(self.api)

        for event in remote_data:
            self.assertEqual(local_data.pop(event["event"]),
                             event["listener_count"])

        self.assertEqual(len(local_data), 0)

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

        self.assertEqual(1, len(test_value))

    def test_get_state(self):
        """ Test Python API get_state. """

        self.assertEqual(
            self.hass.states.get('test.test'),
            remote.get_state(self.api, 'test.test'))

    def test_get_states(self):
        """ Test Python API get_state_entity_ids. """

        self.assertEqual(
            remote.get_states(self.api), self.hass.states.all())

    def test_set_state(self):
        """ Test Python API set_state. """
        self.assertTrue(remote.set_state(self.api, 'test.test', 'set_test'))

        self.assertEqual('set_test', self.hass.states.get('test.test').state)

    def test_is_state(self):
        """ Test Python API is_state. """

        self.assertTrue(
            remote.is_state(self.api, 'test.test',
                            self.hass.states.get('test.test').state))

    def test_get_services(self):
        """ Test Python API get_services. """

        local_services = self.hass.services.services

        for serv_domain in remote.get_services(self.api):
            local = local_services.pop(serv_domain["domain"])

            self.assertEqual(local, serv_domain["services"])

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

        self.assertEqual(1, len(test_value))


class TestRemoteClasses(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()
        cls.slave = ensure_slave_started()

    def test_statemachine_init(self):
        """ Tests if remote.StateMachine copies all states on init. """
        self.assertEqual(len(self.hass.states.all()),
                         len(self.slave.states.all()))

        for state in self.hass.states.all():
            self.assertEqual(
                state, self.slave.states.get(state.entity_id))

    def test_statemachine_set(self):
        """ Tests if setting the state on a slave is recorded. """
        self.slave.states.set("remote.test", "remote.statemachine test")

        # Allow interaction between 2 instances
        time.sleep(1)

        self.assertEqual("remote.statemachine test",
                         self.slave.states.get("remote.test").state)

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

        self.assertEqual(1, len(test_value))
