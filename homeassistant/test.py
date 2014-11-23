"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""
# pylint: disable=protected-access,too-many-public-methods

import os
import unittest
import time
import json
import threading
from datetime import datetime

import requests

import homeassistant as ha
import homeassistant.loader as loader
import homeassistant.util as util
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

        HAHelper.slave = slave

    return HAHelper.slave


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
        blocking_thread = threading.Thread(target=self.hass.block_till_stopped)

        self.assertFalse(blocking_thread.is_alive())

        blocking_thread.start()
        # Python will now give attention to the other thread
        time.sleep(.01)

        self.assertTrue(blocking_thread.is_alive())

        self.hass.call_service(ha.DOMAIN, ha.SERVICE_HOMEASSISTANT_STOP)
        self.hass._pool.block_till_done()

        # hass.block_till_stopped checks every second if it should quit
        # we have to wait worst case 1 second
        wait_loops = 0
        while blocking_thread.is_alive() and wait_loops < 10:
            wait_loops += 1
            time.sleep(0.1)

        self.assertFalse(blocking_thread.is_alive())

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
        # 2 lists to track how often our callbacks got called
        specific_runs = []
        wildcard_runs = []

        self.hass.track_state_change(
            'light.Bowl', lambda a, b, c: specific_runs.append(1), 'on', 'off')

        self.hass.track_state_change(
            'light.Bowl', lambda a, b, c: wildcard_runs.append(1),
            ha.MATCH_ALL, ha.MATCH_ALL)

        # Set same state should not trigger a state change/listener
        self.hass.states.set('light.Bowl', 'on')
        self.hass._pool.block_till_done()
        self.assertEqual(0, len(specific_runs))
        self.assertEqual(0, len(wildcard_runs))

        # State change off -> on
        self.hass.states.set('light.Bowl', 'off')
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        # State change off -> off
        self.hass.states.set('light.Bowl', 'off', {"some_attr": 1})
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        # State change off -> on
        self.hass.states.set('light.Bowl', 'on')
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def test_listen_once_event(self):
        """ Test listen_once_event method. """
        runs = []

        self.hass.listen_once_event('test_event', lambda x: runs.append(1))

        self.hass.bus.fire('test_event')
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(runs))

        # Second time it should not increase runs
        self.hass.bus.fire('test_event')
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(runs))

    def test_track_point_in_time(self):
        """ Test track point in time. """
        before_birthday = datetime(1985, 7, 9, 12, 0, 0)
        birthday_paulus = datetime(1986, 7, 9, 12, 0, 0)
        after_birthday = datetime(1987, 7, 9, 12, 0, 0)

        runs = []

        self.hass.track_point_in_time(
            lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(before_birthday)
        self.hass._pool.block_till_done()
        self.assertEqual(0, len(runs))

        self._send_time_changed(birthday_paulus)
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(runs))

        # A point in time tracker will only fire once, this should do nothing
        self._send_time_changed(birthday_paulus)
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(runs))

        self.hass.track_point_in_time(
            lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(after_birthday)
        self.hass._pool.block_till_done()
        self.assertEqual(2, len(runs))

    def test_track_time_change(self):
        """ Test tracking time change. """
        wildcard_runs = []
        specific_runs = []

        self.hass.track_time_change(lambda x: wildcard_runs.append(1))
        self.hass.track_time_change(
            lambda x: specific_runs.append(1), second=[0, 30])

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 0))
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 15))
        self.hass._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 30))
        self.hass._pool.block_till_done()
        self.assertEqual(2, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def _send_time_changed(self, now):
        """ Send a time changed event. """
        self.hass.bus.fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: now})


class TestEvent(unittest.TestCase):
    """ Test Event class. """
    def test_repr(self):
        """ Test that repr method works. #MoreCoverage """
        self.assertEqual(
            "<Event TestEvent[L]>",
            str(ha.Event("TestEvent")))

        self.assertEqual(
            "<Event TestEvent[R]: beer=nice>",
            str(ha.Event("TestEvent",
                         {"beer": "nice"},
                         ha.EventOrigin.remote)))


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

        # Try deleting a non registered listener, nothing should happen
        self.bus.remove_listener('test', lambda x: len)

        # Remove listener
        self.bus.remove_listener('test', listener)
        self.assertEqual(old_count, len(self.bus.listeners))

        # Try deleting listener while category doesn't exist either
        self.bus.remove_listener('test', listener)


class TestState(unittest.TestCase):
    """ Test EventBus methods. """

    def test_init(self):
        """ Test state.init """
        self.assertRaises(
            ha.InvalidEntityFormatError, ha.State,
            'invalid_entity_format', 'test_state')

    def test_repr(self):
        """ Test state.repr """
        self.assertEqual("<state on @ 12:00:00 08-12-1984>",
                         str(ha.State(
                             "happy.happy", "on",
                             last_changed=datetime(1984, 12, 8, 12, 0, 0))))

        self.assertEqual("<state on:brightness=144 @ 12:00:00 08-12-1984>",
                         str(ha.State("happy.happy", "on", {"brightness": 144},
                                      datetime(1984, 12, 8, 12, 0, 0))))


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


class TestServiceCall(unittest.TestCase):
    """ Test ServiceCall class. """
    def test_repr(self):
        """ Test repr method. """
        self.assertEqual(
            "<ServiceCall homeassistant.start>",
            str(ha.ServiceCall('homeassistant', 'start')))

        self.assertEqual(
            "<ServiceCall homeassistant.start: fast=yes>",
            str(ha.ServiceCall('homeassistant', 'start', {"fast": "yes"})))


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


class TestLoader(unittest.TestCase):
    """ Test the loader module. """
    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        loader.prepare(self.hass)

    def test_get_component(self):
        """ Test if get_component works. """
        self.assertEqual(http, loader.get_component('http'))


class TestUtil(unittest.TestCase):
    """ Tests util methods. """
    def test_sanitize_filename(self):
        """ Test sanitize_filename. """
        self.assertEqual("test", util.sanitize_filename("test"))
        self.assertEqual("test", util.sanitize_filename("/test"))
        self.assertEqual("test", util.sanitize_filename("..test"))
        self.assertEqual("test", util.sanitize_filename("\\test"))
        self.assertEqual("test", util.sanitize_filename("\\../test"))

    def test_sanitize_path(self):
        """ Test sanitize_path. """
        self.assertEqual("test/path", util.sanitize_path("test/path"))
        self.assertEqual("test/path", util.sanitize_path("~test/path"))
        self.assertEqual("//test/path",
                         util.sanitize_path("~/../test/path"))

    def test_slugify(self):
        """ Test slugify. """
        self.assertEqual("Test", util.slugify("T-!@#$!#@$!$est"))
        self.assertEqual("Test_More", util.slugify("Test More"))
        self.assertEqual("Test_More", util.slugify("Test_(More)"))

    def test_datetime_to_str(self):
        """ Test datetime_to_str. """
        self.assertEqual("12:00:00 09-07-1986",
                         util.datetime_to_str(datetime(1986, 7, 9, 12, 0, 0)))

    def test_str_to_datetime(self):
        """ Test str_to_datetime. """
        self.assertEqual(datetime(1986, 7, 9, 12, 0, 0),
                         util.str_to_datetime("12:00:00 09-07-1986"))

    def test_split_entity_id(self):
        """ Test split_entity_id. """
        self.assertEqual(['domain', 'object_id'],
                         util.split_entity_id('domain.object_id'))

    def test_repr_helper(self):
        """ Test repr_helper. """
        self.assertEqual("A", util.repr_helper("A"))
        self.assertEqual("5", util.repr_helper(5))
        self.assertEqual("True", util.repr_helper(True))
        self.assertEqual("test=1, more=2",
                         util.repr_helper({"test": 1, "more": 2}))
        self.assertEqual("12:00:00 09-07-1986",
                         util.repr_helper(datetime(1986, 7, 9, 12, 0, 0)))

    # pylint: disable=invalid-name
    def test_color_RGB_to_xy(self):
        """ Test color_RGB_to_xy. """
        self.assertEqual((0, 0), util.color_RGB_to_xy(0, 0, 0))
        self.assertEqual((0.3127159072215825, 0.3290014805066623),
                         util.color_RGB_to_xy(255, 255, 255))

        self.assertEqual((0.15001662234042554, 0.060006648936170214),
                         util.color_RGB_to_xy(0, 0, 255))

        self.assertEqual((0.3, 0.6), util.color_RGB_to_xy(0, 255, 0))

        self.assertEqual((0.6400744994567747, 0.3299705106316933),
                         util.color_RGB_to_xy(255, 0, 0))

    def test_convert(self):
        """ Test convert. """
        self.assertEqual(5, util.convert("5", int))
        self.assertEqual(5.0, util.convert("5", float))
        self.assertEqual(True, util.convert("True", bool))
        self.assertEqual(1, util.convert("NOT A NUMBER", int, 1))
        self.assertEqual(1, util.convert(None, int, 1))

    def test_ensure_unique_string(self):
        """ Test ensure_unique_string. """
        self.assertEqual(
            "Beer_3",
            util.ensure_unique_string("Beer", ["Beer", "Beer_2"]))


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

        self.hass._pool.block_till_done()

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

        self.hass._pool.block_till_done()

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

        self.hass._pool.block_till_done()

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

        self.hass._pool.block_till_done()

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

        self.hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))


class TestRemoteMethods(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()

        cls.api = remote.API("127.0.0.1", API_PASSWORD)

    def test_validate_api(self):
        """ Test Python API validate_api. """
        self.assertEqual(remote.APIStatus.OK, remote.validate_api(self.api))

        self.assertEqual(remote.APIStatus.INVALID_PASSWORD,
                         remote.validate_api(
                             remote.API("127.0.0.1", API_PASSWORD + "A")))

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

        self.hass._pool.block_till_done()

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

        self.hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))


class TestRemoteClasses(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    @classmethod
    def setUpClass(cls):    # pylint: disable=invalid-name
        """ things to be run when tests are started. """
        cls.hass = ensure_homeassistant_started()
        cls.slave = ensure_slave_started()

    def test_home_assistant_init(self):
        """ Test HomeAssistant init. """
        self.assertRaises(
            ha.HomeAssistantError, remote.HomeAssistant,
            remote.API('127.0.0.1', API_PASSWORD + 'A', 8124))

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

        # Wait till slave tells master
        self.slave._pool.block_till_done()
        # Wait till master gives updated state
        self.hass._pool.block_till_done()

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

        # Wait till slave tells master
        self.slave._pool.block_till_done()
        # Wait till master gives updated event
        self.hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))
