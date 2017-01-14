"""The tests for the Alert component."""
# pylint: disable=protected-access
from copy import deepcopy
import unittest

from homeassistant.bootstrap import setup_component
from homeassistant.core import callback
import homeassistant.components.alert as alert
import homeassistant.components.notify as notify
from homeassistant.const import (CONF_ENTITY_ID, STATE_IDLE, CONF_NAME,
                                 CONF_STATE, STATE_ON, STATE_OFF)

from tests.common import get_test_home_assistant

NAME = "alert_test"
NOTIFIER = 'test'
TEST_CONFIG = \
    {alert.DOMAIN: {
        NAME: {
            CONF_NAME: NAME,
            CONF_ENTITY_ID: "sensor.test",
            CONF_STATE: STATE_ON,
            alert.CONF_REPEAT: 30,
            alert.CONF_SKIP_FIRST: False,
            alert.CONF_NOTIFIERS: [NOTIFIER]}
        }}
TEST_BACKOFF = [NAME, NAME, "sensor.test", STATE_ON,
                30, False, NOTIFIER, True, 1.5]
TEST_NOACK = [NAME, NAME, "sensor.test", STATE_ON,
              30, False, NOTIFIER, False, 1.0]
ENTITY_ID = alert.ENTITY_ID_FORMAT.format(NAME)


# pylint: disable=invalid-name
class TestAlert(unittest.TestCase):
    """Test the alert module."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_on(self):
        """Test is_on method."""
        self.hass.states.set(ENTITY_ID, STATE_ON)
        self.hass.block_till_done()
        self.assertTrue(alert.is_on(self.hass, ENTITY_ID))
        self.hass.states.set(ENTITY_ID, STATE_OFF)
        self.hass.block_till_done()
        self.assertFalse(alert.is_on(self.hass, ENTITY_ID))

    def test_setup(self):
        """Test setup method."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.assertEqual(STATE_IDLE, self.hass.states.get(ENTITY_ID).state)

    def test_fire(self):
        """Test the alert firing."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(STATE_ON, self.hass.states.get(ENTITY_ID).state)

    def test_silence(self):
        """Test silencing the alert."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        alert.turn_off(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertEqual(STATE_OFF, self.hass.states.get(ENTITY_ID).state)

        # alert should not be silenced on next fire
        self.hass.states.set("sensor.test", STATE_OFF)
        self.hass.block_till_done()
        self.assertEqual(STATE_IDLE, self.hass.states.get(ENTITY_ID).state)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(STATE_ON, self.hass.states.get(ENTITY_ID).state)

    def test_reset(self):
        """Test resetting the alert."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        alert.turn_off(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertEqual(STATE_OFF, self.hass.states.get(ENTITY_ID).state)
        alert.turn_on(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertEqual(STATE_ON, self.hass.states.get(ENTITY_ID).state)

    def test_toggle(self):
        """Test toggling alert."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(STATE_ON, self.hass.states.get(ENTITY_ID).state)
        alert.toggle(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertEqual(STATE_OFF, self.hass.states.get(ENTITY_ID).state)
        alert.toggle(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        self.assertEqual(STATE_ON, self.hass.states.get(ENTITY_ID).state)

    def test_hidden(self):
        """Test entity hidding."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        hidden = self.hass.states.get(ENTITY_ID).attributes.get('hidden')
        self.assertTrue(hidden)

        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        hidden = self.hass.states.get(ENTITY_ID).attributes.get('hidden')
        self.assertFalse(hidden)

        alert.turn_off(self.hass, ENTITY_ID)
        hidden = self.hass.states.get(ENTITY_ID).attributes.get('hidden')
        self.assertFalse(hidden)

    def test_notification(self):
        """Test notifications."""
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.services.register(
            notify.DOMAIN, NOTIFIER, record_event)

        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.assertEqual(0, len(events))

        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(1, len(events))

        self.hass.states.set("sensor.test", STATE_OFF)
        self.hass.block_till_done()
        self.assertEqual(1, len(events))

    def test_skipfirst(self):
        """Test skipping first notification."""
        config = deepcopy(TEST_CONFIG)
        config[alert.DOMAIN][NAME][alert.CONF_SKIP_FIRST] = True
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.services.register(
            notify.DOMAIN, NOTIFIER, record_event)

        assert setup_component(self.hass, alert.DOMAIN, config)
        self.assertEqual(0, len(events))

        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(0, len(events))

    def test_backoff(self):
        """Test backoff feature."""
        entity = alert.Alert(self.hass, *TEST_BACKOFF)
        self.hass.async_add_job(entity.begin_alerting)
        self.hass.block_till_done()
        self.assertEqual(30 * 60 * 1.5, entity._next_delay.seconds)

        self.hass.async_add_job(entity._notify())
        self.hass.block_till_done()
        self.assertEqual(30 * 60 * 1.5 * 1.5, entity._next_delay.seconds)

    def test_noack(self):
        """Test no ack feature."""
        entity = alert.Alert(self.hass, *TEST_NOACK)
        self.hass.async_add_job(entity.begin_alerting)
        self.hass.block_till_done()

        self.assertEqual(True, entity.hidden)
