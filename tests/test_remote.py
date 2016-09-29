"""Test Home Assistant remote methods and classes."""
# pylint: disable=protected-access,too-many-public-methods
import asyncio
import threading
import time
import unittest
from unittest.mock import patch

import homeassistant.core as ha
import homeassistant.bootstrap as bootstrap
import homeassistant.remote as remote
import homeassistant.components.http as http
from homeassistant.const import HTTP_HEADER_HA_AUTH, EVENT_STATE_CHANGED
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_instance_port, get_test_home_assistant, get_test_config_dir)

API_PASSWORD = "test1234"
MASTER_PORT = get_test_instance_port()
SLAVE_PORT = get_test_instance_port()
BROKEN_PORT = get_test_instance_port()
HTTP_BASE_URL = "http://127.0.0.1:{}".format(MASTER_PORT)

HA_HEADERS = {HTTP_HEADER_HA_AUTH: API_PASSWORD}

broken_api = remote.API('127.0.0.1', "bladiebla")
hass, slave, master_api = None, None, None


def _url(path=""):
    """Helper method to generate URLs."""
    return HTTP_BASE_URL + path


def setUpModule():   # pylint: disable=invalid-name
    """Initalization of a Home Assistant server and Slave instance."""
    global hass, slave, master_api

    hass = get_test_home_assistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: MASTER_PORT}})

    bootstrap.setup_component(hass, 'api')

    hass.start()
    time.sleep(0.05)

    master_api = remote.API("127.0.0.1", API_PASSWORD, MASTER_PORT)

    # Start slave
    loop = asyncio.new_event_loop()

    # FIXME: should not be a daemon
    threading.Thread(name="SlaveThread", daemon=True,
                     target=loop.run_forever).start()

    slave = remote.HomeAssistant(master_api, loop=loop)
    slave.config.config_dir = get_test_config_dir()
    slave.config.skip_pip = True
    bootstrap.setup_component(
        slave, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: SLAVE_PORT}})

    with patch.object(ha, 'async_create_timer', return_value=None):
        slave.start()


def tearDownModule():   # pylint: disable=invalid-name
    """Stop the Home Assistant server and slave."""
    slave.stop()
    hass.stop()


class TestRemoteMethods(unittest.TestCase):
    """Test the homeassistant.remote module."""

    def tearDown(self):
        """Stop everything that was started."""
        slave.block_till_done()
        hass.block_till_done()

    def test_validate_api(self):
        """Test Python API validate_api."""
        self.assertEqual(remote.APIStatus.OK, remote.validate_api(master_api))

        self.assertEqual(
            remote.APIStatus.INVALID_PASSWORD,
            remote.validate_api(
                remote.API("127.0.0.1", API_PASSWORD + "A", MASTER_PORT)))

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
        hass.bus.listen(EVENT_STATE_CHANGED, events.append)

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


class TestRemoteClasses(unittest.TestCase):
    """Test the homeassistant.remote module."""

    def tearDown(self):
        """Stop everything that was started."""
        slave.block_till_done()
        hass.block_till_done()

    def test_home_assistant_init(self):
        """Test HomeAssistant init."""
        # Wrong password
        self.assertRaises(
            ha.HomeAssistantError, remote.HomeAssistant,
            remote.API('127.0.0.1', API_PASSWORD + 'A', 8124))

        # Wrong port
        self.assertRaises(
            ha.HomeAssistantError, remote.HomeAssistant,
            remote.API('127.0.0.1', API_PASSWORD, BROKEN_PORT))

    def test_statemachine_init(self):
        """Test if remote.StateMachine copies all states on init."""
        self.assertEqual(sorted(hass.states.all()),
                         sorted(slave.states.all()))

    def test_statemachine_set(self):
        """Test if setting the state on a slave is recorded."""
        slave.states.set("remote.test", "remote.statemachine test")

        # Wait till slave tells master
        slave.block_till_done()
        # Wait till master gives updated state
        hass.block_till_done()

        self.assertEqual("remote.statemachine test",
                         slave.states.get("remote.test").state)

    def test_statemachine_remove_from_master(self):
        """Remove statemachine from master."""
        hass.states.set("remote.master_remove", "remove me!")
        hass.block_till_done()
        slave.block_till_done()

        self.assertIn('remote.master_remove', slave.states.entity_ids())

        hass.states.remove("remote.master_remove")
        hass.block_till_done()
        slave.block_till_done()

        self.assertNotIn('remote.master_remove', slave.states.entity_ids())

    def test_statemachine_remove_from_slave(self):
        """Remove statemachine from slave."""
        hass.states.set("remote.slave_remove", "remove me!")
        hass.block_till_done()

        self.assertIn('remote.slave_remove', slave.states.entity_ids())

        self.assertTrue(slave.states.remove("remote.slave_remove"))
        slave.block_till_done()
        hass.block_till_done()

        self.assertNotIn('remote.slave_remove', slave.states.entity_ids())

    def test_eventbus_fire(self):
        """Test if events fired from the eventbus get fired."""
        hass_call = []
        slave_call = []

        hass.bus.listen("test.event_no_data", lambda _: hass_call.append(1))
        slave.bus.listen("test.event_no_data", lambda _: slave_call.append(1))
        slave.bus.fire("test.event_no_data")

        # Wait till slave tells master
        slave.block_till_done()
        # Wait till master gives updated event
        hass.block_till_done()

        self.assertEqual(1, len(hass_call))
        self.assertEqual(1, len(slave_call))

    def test_get_config(self):
        """Test the return of the configuration."""
        self.assertEqual(hass.config.as_dict(), remote.get_config(master_api))
