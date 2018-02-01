"""Test Home Assistant remote methods and classes."""
# pylint: disable=protected-access
import unittest

from homeassistant import remote, setup, core as ha
import homeassistant.components.http as http
from homeassistant.const import HTTP_HEADER_HA_AUTH, EVENT_STATE_CHANGED
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_instance_port, get_test_home_assistant)

API_PASSWORD = 'test1234'
MASTER_PORT = get_test_instance_port()
BROKEN_PORT = get_test_instance_port()
HTTP_BASE_URL = 'http://127.0.0.1:{}'.format(MASTER_PORT)

HA_HEADERS = {HTTP_HEADER_HA_AUTH: API_PASSWORD}

broken_api = remote.API('127.0.0.1', "bladybla", port=get_test_instance_port())
hass, master_api = None, None


def _url(path=''):
    """Helper method to generate URLs."""
    return HTTP_BASE_URL + path


# pylint: disable=invalid-name
def setUpModule():
    """Initialization of a Home Assistant server instance."""
    global hass, master_api

    hass = get_test_home_assistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    setup.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: MASTER_PORT}})

    setup.setup_component(hass, 'api')

    hass.start()

    master_api = remote.API('127.0.0.1', API_PASSWORD, MASTER_PORT)


# pylint: disable=invalid-name
def tearDownModule():
    """Stop the Home Assistant server."""
    hass.stop()


class TestRemoteMethods(unittest.TestCase):
    """Test the homeassistant.remote module."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_validate_api(self):
        """Test Python API validate_api."""
        self.assertEqual(remote.APIStatus.OK, remote.validate_api(master_api))

        self.assertEqual(
            remote.APIStatus.INVALID_PASSWORD,
            remote.validate_api(
                remote.API('127.0.0.1', API_PASSWORD + 'A', MASTER_PORT)))

        self.assertEqual(
            remote.APIStatus.CANNOT_CONNECT, remote.validate_api(broken_api))

    def test_get_event_listeners(self):
        """Test Python API get_event_listeners."""
        local_data = hass.bus.listeners
        remote_data = remote.get_event_listeners(master_api)

        for event in remote_data:
            self.assertEqual(local_data.pop(event["event"]),
                             event["listener_count"])

        self.assertEqual(len(local_data), 0)

        self.assertEqual({}, remote.get_event_listeners(broken_api))

    def test_fire_event(self):
        """Test Python API fire_event."""
        test_value = []

        @ha.callback
        def listener(event):
            """Helper method that will verify our event got called."""
            test_value.append(1)

        hass.bus.listen("test.event_no_data", listener)
        remote.fire_event(master_api, "test.event_no_data")
        hass.block_till_done()
        self.assertEqual(1, len(test_value))

        # Should not trigger any exception
        remote.fire_event(broken_api, "test.event_no_data")

    def test_get_state(self):
        """Test Python API get_state."""
        self.assertEqual(
            hass.states.get('test.test'),
            remote.get_state(master_api, 'test.test'))

        self.assertEqual(None, remote.get_state(broken_api, 'test.test'))

    def test_get_states(self):
        """Test Python API get_state_entity_ids."""
        self.assertEqual(hass.states.all(), remote.get_states(master_api))
        self.assertEqual([], remote.get_states(broken_api))

    def test_remove_state(self):
        """Test Python API set_state."""
        hass.states.set('test.remove_state', 'set_test')

        self.assertIn('test.remove_state', hass.states.entity_ids())
        remote.remove_state(master_api, 'test.remove_state')
        self.assertNotIn('test.remove_state', hass.states.entity_ids())

    def test_set_state(self):
        """Test Python API set_state."""
        remote.set_state(master_api, 'test.test', 'set_test')

        state = hass.states.get('test.test')

        self.assertIsNotNone(state)
        self.assertEqual('set_test', state.state)

        self.assertFalse(remote.set_state(broken_api, 'test.test', 'set_test'))

    def test_set_state_with_push(self):
        """Test Python API set_state with push option."""
        events = []
        hass.bus.listen(EVENT_STATE_CHANGED, lambda ev: events.append(ev))

        remote.set_state(master_api, 'test.test', 'set_test_2')
        remote.set_state(master_api, 'test.test', 'set_test_2')
        hass.block_till_done()
        self.assertEqual(1, len(events))

        remote.set_state(
            master_api, 'test.test', 'set_test_2', force_update=True)
        hass.block_till_done()
        self.assertEqual(2, len(events))

    def test_is_state(self):
        """Test Python API is_state."""
        self.assertTrue(
            remote.is_state(master_api, 'test.test',
                            hass.states.get('test.test').state))

        self.assertFalse(
            remote.is_state(broken_api, 'test.test',
                            hass.states.get('test.test').state))

    def test_get_services(self):
        """Test Python API get_services."""
        local_services = hass.services.services

        for serv_domain in remote.get_services(master_api):
            local = local_services.pop(serv_domain["domain"])

            self.assertEqual(local, serv_domain["services"])

        self.assertEqual({}, remote.get_services(broken_api))

    def test_call_service(self):
        """Test Python API services.call."""
        test_value = []

        @ha.callback
        def listener(service_call):
            """Helper method that will verify that our service got called."""
            test_value.append(1)

        hass.services.register("test_domain", "test_service", listener)

        remote.call_service(master_api, "test_domain", "test_service")

        hass.block_till_done()

        self.assertEqual(1, len(test_value))

        # Should not raise an exception
        remote.call_service(broken_api, "test_domain", "test_service")

    def test_json_encoder(self):
        """Test the JSON Encoder."""
        ha_json_enc = remote.JSONEncoder()
        state = hass.states.get('test.test')

        self.assertEqual(state.as_dict(), ha_json_enc.default(state))

        # Default method raises TypeError if non HA object
        self.assertRaises(TypeError, ha_json_enc.default, 1)

        now = dt_util.utcnow()
        self.assertEqual(now.isoformat(), ha_json_enc.default(now))
