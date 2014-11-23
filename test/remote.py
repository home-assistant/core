"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""
# pylint: disable=protected-access,too-many-public-methods
import unittest

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
        print("Setting up new HA")
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
