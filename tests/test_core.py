"""
tests.test_core
~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant core works.
"""
# pylint: disable=protected-access,too-many-public-methods
# pylint: disable=too-few-public-methods
import os
import unittest
import time
import threading
from datetime import datetime

import homeassistant as ha


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

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        try:
            self.hass.stop()
        except ha.HomeAssistantError:
            # Already stopped after the block till stopped test
            pass

    def test_get_config_path(self):
        """ Test get_config_path method. """
        self.assertEqual(os.path.join(os.getcwd(), "config"),
                         self.hass.config.config_dir)

        self.assertEqual(os.path.join(os.getcwd(), "config", "test.conf"),
                         self.hass.config.path("test.conf"))

    def test_block_till_stoped(self):
        """ Test if we can block till stop service is called. """
        blocking_thread = threading.Thread(target=self.hass.block_till_stopped)

        self.assertFalse(blocking_thread.is_alive())

        blocking_thread.start()
        # Python will now give attention to the other thread
        time.sleep(1)

        self.assertTrue(blocking_thread.is_alive())

        self.hass.services.call(ha.DOMAIN, ha.SERVICE_HOMEASSISTANT_STOP)
        self.hass.pool.block_till_done()

        # hass.block_till_stopped checks every second if it should quit
        # we have to wait worst case 1 second
        wait_loops = 0
        while blocking_thread.is_alive() and wait_loops < 50:
            wait_loops += 1
            time.sleep(0.1)

        self.assertFalse(blocking_thread.is_alive())

    def test_track_point_in_time(self):
        """ Test track point in time. """
        before_birthday = datetime(1985, 7, 9, 12, 0, 0)
        birthday_paulus = datetime(1986, 7, 9, 12, 0, 0)
        after_birthday = datetime(1987, 7, 9, 12, 0, 0)

        runs = []

        self.hass.track_point_in_utc_time(
            lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(before_birthday)
        self.hass.pool.block_till_done()
        self.assertEqual(0, len(runs))

        self._send_time_changed(birthday_paulus)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(runs))

        # A point in time tracker will only fire once, this should do nothing
        self._send_time_changed(birthday_paulus)
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(runs))

        self.hass.track_point_in_utc_time(
            lambda x: runs.append(1), birthday_paulus)

        self._send_time_changed(after_birthday)
        self.hass.pool.block_till_done()
        self.assertEqual(2, len(runs))

    def test_track_time_change(self):
        """ Test tracking time change. """
        wildcard_runs = []
        specific_runs = []

        self.hass.track_time_change(lambda x: wildcard_runs.append(1))
        self.hass.track_time_change(
            lambda x: specific_runs.append(1), second=[0, 30])

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 0))
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 15))
        self.hass.pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        self._send_time_changed(datetime(2014, 5, 24, 12, 0, 30))
        self.hass.pool.block_till_done()
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

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.bus._pool.stop()

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

    def test_listen_once_event(self):
        """ Test listen_once_event method. """
        runs = []

        self.bus.listen_once('test_event', lambda x: runs.append(1))

        self.bus.fire('test_event')
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(runs))

        # Second time it should not increase runs
        self.bus.fire('test_event')
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(runs))


class TestState(unittest.TestCase):
    """ Test EventBus methods. """

    def test_init(self):
        """ Test state.init """
        self.assertRaises(
            ha.InvalidEntityFormatError, ha.State,
            'invalid_entity_format', 'test_state')

    def test_repr(self):
        """ Test state.repr """
        self.assertEqual("<state happy.happy=on @ 12:00:00 08-12-1984>",
                         str(ha.State(
                             "happy.happy", "on",
                             last_changed=datetime(1984, 12, 8, 12, 0, 0))))

        self.assertEqual(
            "<state happy.happy=on; brightness=144 @ 12:00:00 08-12-1984>",
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

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.bus._pool.stop()

    def test_is_state(self):
        """ Test is_state method. """
        self.assertTrue(self.states.is_state('light.Bowl', 'on'))
        self.assertFalse(self.states.is_state('light.Bowl', 'off'))
        self.assertFalse(self.states.is_state('light.Non_existing', 'on'))

    def test_entity_ids(self):
        """ Test get_entity_ids method. """
        ent_ids = self.states.entity_ids()
        self.assertEqual(2, len(ent_ids))
        self.assertTrue('light.bowl' in ent_ids)
        self.assertTrue('switch.ac' in ent_ids)

        ent_ids = self.states.entity_ids('light')
        self.assertEqual(1, len(ent_ids))
        self.assertTrue('light.bowl' in ent_ids)

    def test_remove(self):
        """ Test remove method. """
        self.assertTrue('light.bowl' in self.states.entity_ids())
        self.assertTrue(self.states.remove('light.bowl'))
        self.assertFalse('light.bowl' in self.states.entity_ids())

        # If it does not exist, we should get False
        self.assertFalse(self.states.remove('light.Bowl'))

    def test_track_change(self):
        """ Test states.track_change. """
        # 2 lists to track how often our callbacks got called
        specific_runs = []
        wildcard_runs = []

        self.states.track_change(
            'light.Bowl', lambda a, b, c: specific_runs.append(1), 'on', 'off')

        self.states.track_change(
            'light.Bowl', lambda a, b, c: wildcard_runs.append(1),
            ha.MATCH_ALL, ha.MATCH_ALL)

        # Set same state should not trigger a state change/listener
        self.states.set('light.Bowl', 'on')
        self.bus._pool.block_till_done()
        self.assertEqual(0, len(specific_runs))
        self.assertEqual(0, len(wildcard_runs))

        # State change off -> on
        self.states.set('light.Bowl', 'off')
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(1, len(wildcard_runs))

        # State change off -> off
        self.states.set('light.Bowl', 'off', {"some_attr": 1})
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(2, len(wildcard_runs))

        # State change off -> on
        self.states.set('light.Bowl', 'on')
        self.bus._pool.block_till_done()
        self.assertEqual(1, len(specific_runs))
        self.assertEqual(3, len(wildcard_runs))

    def test_case_insensitivty(self):
        runs = []

        self.states.track_change(
            'light.BoWl', lambda a, b, c: runs.append(1),
            ha.MATCH_ALL, ha.MATCH_ALL)

        self.states.set('light.BOWL', 'off')
        self.bus._pool.block_till_done()

        self.assertTrue(self.states.is_state('light.bowl', 'off'))
        self.assertEqual(1, len(runs))

    def test_last_changed_not_updated_on_same_state(self):
        state = self.states.get('light.Bowl')

        time.sleep(1)

        self.states.set("light.Bowl", "on")

        self.assertEqual(state.last_changed,
                         self.states.get('light.Bowl').last_changed)


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
        self.pool = ha.create_worker_pool()
        self.bus = ha.EventBus(self.pool)
        self.services = ha.ServiceRegistry(self.bus, self.pool)
        self.services.register("test_domain", "test_service", lambda x: len)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.pool.stop()

    def test_has_service(self):
        """ Test has_service method. """
        self.assertTrue(
            self.services.has_service("test_domain", "test_service"))
