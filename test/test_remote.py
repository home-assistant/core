"""
test.remote
~~~~~~~~~~~

Tests Home Assistant remote methods and classes.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
import logging

import homeassistant as ha
import homeassistant.remote as remote
import homeassistant.components.http as http

API_PASSWORD = "test1234"

HTTP_BASE_URL = "http://127.0.0.1:{}".format(remote.SERVER_PORT)

HA_HEADERS = {remote.AUTH_HEADER: API_PASSWORD}


def _url(path=""):
    """ Helper method to generate urls. """
    return HTTP_BASE_URL + path


def setUpModule():
    """ Initalizes a Home Assistant server and Slave instance. """
    global hass, slave, master_api

    hass = ha.HomeAssistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    http.setup(hass,
               {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD}})

    hass.start()

    master_api = remote.API("127.0.0.1", API_PASSWORD)

    # Start slave
    local_api = remote.API("127.0.0.1", API_PASSWORD, 8124)
    slave = remote.HomeAssistant(master_api, local_api)

    http.setup(slave,
               {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                              http.CONF_SERVER_PORT: 8124}})

    slave.start()


def tearDownModule():
    """ Stops the Home Assistant server and slave. """
    global hass, slave

    hass.stop()
    slave.stop()


class TestRemoteMethods(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    def test_validate_api(self):
        """ Test Python API validate_api. """
        self.assertEqual(remote.APIStatus.OK, remote.validate_api(master_api))

        self.assertEqual(remote.APIStatus.INVALID_PASSWORD,
                         remote.validate_api(
                             remote.API("127.0.0.1", API_PASSWORD + "A")))

    def test_get_event_listeners(self):
        """ Test Python API get_event_listeners. """
        local_data = hass.bus.listeners
        remote_data = remote.get_event_listeners(master_api)

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

        hass.listen_once_event("test.event_no_data", listener)

        remote.fire_event(master_api, "test.event_no_data")

        hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))

    def test_get_state(self):
        """ Test Python API get_state. """

        self.assertEqual(
            hass.states.get('test.test'),
            remote.get_state(master_api, 'test.test'))

    def test_get_states(self):
        """ Test Python API get_state_entity_ids. """

        self.assertEqual(
            remote.get_states(master_api), hass.states.all())

    def test_set_state(self):
        """ Test Python API set_state. """
        self.assertTrue(remote.set_state(master_api, 'test.test', 'set_test'))

        self.assertEqual('set_test', hass.states.get('test.test').state)

    def test_is_state(self):
        """ Test Python API is_state. """

        self.assertTrue(
            remote.is_state(master_api, 'test.test',
                            hass.states.get('test.test').state))

    def test_get_services(self):
        """ Test Python API get_services. """

        local_services = hass.services.services

        for serv_domain in remote.get_services(master_api):
            local = local_services.pop(serv_domain["domain"])

            self.assertEqual(local, serv_domain["services"])

    def test_call_service(self):
        """ Test Python API call_service. """
        test_value = []

        def listener(service_call):   # pylint: disable=unused-argument
            """ Helper method that will verify that our service got called. """
            test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        remote.call_service(master_api, "test_domain", "test_service")

        hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))


class TestRemoteClasses(unittest.TestCase):
    """ Test the homeassistant.remote module. """

    def test_home_assistant_init(self):
        """ Test HomeAssistant init. """
        self.assertRaises(
            ha.HomeAssistantError, remote.HomeAssistant,
            remote.API('127.0.0.1', API_PASSWORD + 'A', 8124))

    def test_statemachine_init(self):
        """ Tests if remote.StateMachine copies all states on init. """
        self.assertEqual(len(hass.states.all()),
                         len(slave.states.all()))

        for state in hass.states.all():
            self.assertEqual(
                state, slave.states.get(state.entity_id))

    def test_statemachine_set(self):
        """ Tests if setting the state on a slave is recorded. """
        slave.states.set("remote.test", "remote.statemachine test")

        # Wait till slave tells master
        slave._pool.block_till_done()
        # Wait till master gives updated state
        hass._pool.block_till_done()

        self.assertEqual("remote.statemachine test",
                         slave.states.get("remote.test").state)

    def test_eventbus_fire(self):
        """ Test if events fired from the eventbus get fired. """
        test_value = []

        def listener(event):   # pylint: disable=unused-argument
            """ Helper method that will verify our event got called. """
            test_value.append(1)

        slave.listen_once_event("test.event_no_data", listener)

        slave.bus.fire("test.event_no_data")

        # Wait till slave tells master
        slave._pool.block_till_done()
        # Wait till master gives updated event
        hass._pool.block_till_done()

        self.assertEqual(1, len(test_value))
