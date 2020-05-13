"""The tests for the Alert component."""
# pylint: disable=protected-access
from copy import deepcopy
import unittest

import homeassistant.components.alert as alert
from homeassistant.components.alert import DOMAIN
import homeassistant.components.notify as notify
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_STATE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

NAME = "alert_test"
DONE_MESSAGE = "alert_gone"
NOTIFIER = "test"
TEMPLATE = "{{ states.sensor.test.entity_id }}"
TEST_ENTITY = "sensor.test"
TITLE = "{{ states.sensor.test.entity_id }}"
TEST_TITLE = "sensor.test"
TEST_DATA = {"data": {"inline_keyboard": ["Close garage:/close_garage"]}}
TEST_CONFIG = {
    alert.DOMAIN: {
        NAME: {
            CONF_NAME: NAME,
            alert.CONF_DONE_MESSAGE: DONE_MESSAGE,
            CONF_ENTITY_ID: TEST_ENTITY,
            CONF_STATE: STATE_ON,
            alert.CONF_REPEAT: 30,
            alert.CONF_SKIP_FIRST: False,
            alert.CONF_NOTIFIERS: [NOTIFIER],
            alert.CONF_TITLE: TITLE,
            alert.CONF_DATA: {},
        }
    }
}
TEST_NOACK = [
    NAME,
    NAME,
    "sensor.test",
    STATE_ON,
    [30],
    False,
    None,
    None,
    NOTIFIER,
    False,
    None,
    None,
]
ENTITY_ID = f"{alert.DOMAIN}.{NAME}"


def turn_on(hass, entity_id):
    """Reset the alert.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.add_job(async_turn_on, hass, entity_id)


@callback
def async_turn_on(hass, entity_id):
    """Async reset the alert.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_ENTITY_ID: entity_id}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data))


def turn_off(hass, entity_id):
    """Acknowledge alert.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.add_job(async_turn_off, hass, entity_id)


@callback
def async_turn_off(hass, entity_id):
    """Async acknowledge the alert.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_ENTITY_ID: entity_id}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data))


def toggle(hass, entity_id):
    """Toggle acknowledgment of alert.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.add_job(async_toggle, hass, entity_id)


@callback
def async_toggle(hass, entity_id):
    """Async toggle acknowledgment of alert.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_ENTITY_ID: entity_id}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_TOGGLE, data))


# pylint: disable=invalid-name
class TestAlert(unittest.TestCase):
    """Test the alert module."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self._setup_notify()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def _setup_notify(self):
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.services.register(notify.DOMAIN, NOTIFIER, record_event)

        return events

    def test_is_on(self):
        """Test is_on method."""
        self.hass.states.set(ENTITY_ID, STATE_ON)
        self.hass.block_till_done()
        assert alert.is_on(self.hass, ENTITY_ID)
        self.hass.states.set(ENTITY_ID, STATE_OFF)
        self.hass.block_till_done()
        assert not alert.is_on(self.hass, ENTITY_ID)

    def test_setup(self):
        """Test setup method."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        assert STATE_IDLE == self.hass.states.get(ENTITY_ID).state

    def test_fire(self):
        """Test the alert firing."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        assert STATE_ON == self.hass.states.get(ENTITY_ID).state

    def test_silence(self):
        """Test silencing the alert."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        turn_off(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        assert STATE_OFF == self.hass.states.get(ENTITY_ID).state

        # alert should not be silenced on next fire
        self.hass.states.set("sensor.test", STATE_OFF)
        self.hass.block_till_done()
        assert STATE_IDLE == self.hass.states.get(ENTITY_ID).state
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        assert STATE_ON == self.hass.states.get(ENTITY_ID).state

    def test_reset(self):
        """Test resetting the alert."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        turn_off(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        assert STATE_OFF == self.hass.states.get(ENTITY_ID).state
        turn_on(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        assert STATE_ON == self.hass.states.get(ENTITY_ID).state

    def test_toggle(self):
        """Test toggling alert."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        assert STATE_ON == self.hass.states.get(ENTITY_ID).state
        toggle(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        assert STATE_OFF == self.hass.states.get(ENTITY_ID).state
        toggle(self.hass, ENTITY_ID)
        self.hass.block_till_done()
        assert STATE_ON == self.hass.states.get(ENTITY_ID).state

    def test_hidden(self):
        """Test entity hiding."""
        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        hidden = self.hass.states.get(ENTITY_ID).attributes.get("hidden")
        assert hidden

        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        hidden = self.hass.states.get(ENTITY_ID).attributes.get("hidden")
        assert not hidden

        turn_off(self.hass, ENTITY_ID)
        hidden = self.hass.states.get(ENTITY_ID).attributes.get("hidden")
        assert not hidden

    def test_notification_no_done_message(self):
        """Test notifications."""
        events = []
        config = deepcopy(TEST_CONFIG)
        del config[alert.DOMAIN][NAME][alert.CONF_DONE_MESSAGE]

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.services.register(notify.DOMAIN, NOTIFIER, record_event)

        assert setup_component(self.hass, alert.DOMAIN, config)
        assert len(events) == 0

        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        assert len(events) == 1

        self.hass.states.set("sensor.test", STATE_OFF)
        self.hass.block_till_done()
        assert len(events) == 1

    def test_notification(self):
        """Test notifications."""
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.services.register(notify.DOMAIN, NOTIFIER, record_event)

        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)
        assert len(events) == 0

        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        assert len(events) == 1

        self.hass.states.set("sensor.test", STATE_OFF)
        self.hass.block_till_done()
        assert len(events) == 2

    def test_sending_non_templated_notification(self):
        """Test notifications."""
        events = self._setup_notify()

        assert setup_component(self.hass, alert.DOMAIN, TEST_CONFIG)

        self.hass.states.set(TEST_ENTITY, STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(1, len(events))
        last_event = events[-1]
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], NAME)

    def test_sending_templated_notification(self):
        """Test templated notification."""
        events = self._setup_notify()

        config = deepcopy(TEST_CONFIG)
        config[alert.DOMAIN][NAME][alert.CONF_ALERT_MESSAGE] = TEMPLATE
        assert setup_component(self.hass, alert.DOMAIN, config)

        self.hass.states.set(TEST_ENTITY, STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(1, len(events))
        last_event = events[-1]
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], TEST_ENTITY)

    def test_sending_templated_done_notification(self):
        """Test templated notification."""
        events = self._setup_notify()

        config = deepcopy(TEST_CONFIG)
        config[alert.DOMAIN][NAME][alert.CONF_DONE_MESSAGE] = TEMPLATE
        assert setup_component(self.hass, alert.DOMAIN, config)

        self.hass.states.set(TEST_ENTITY, STATE_ON)
        self.hass.block_till_done()
        self.hass.states.set(TEST_ENTITY, STATE_OFF)
        self.hass.block_till_done()
        self.assertEqual(2, len(events))
        last_event = events[-1]
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], TEST_ENTITY)

    def test_sending_titled_notification(self):
        """Test notifications."""
        events = self._setup_notify()

        config = deepcopy(TEST_CONFIG)
        config[alert.DOMAIN][NAME][alert.CONF_TITLE] = TITLE
        assert setup_component(self.hass, alert.DOMAIN, config)

        self.hass.states.set(TEST_ENTITY, STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(1, len(events))
        last_event = events[-1]
        self.assertEqual(last_event.data[notify.ATTR_TITLE], TEST_TITLE)

    def test_sending_data_notification(self):
        """Test notifications."""
        events = self._setup_notify()

        config = deepcopy(TEST_CONFIG)
        config[alert.DOMAIN][NAME][alert.CONF_DATA] = TEST_DATA
        assert setup_component(self.hass, alert.DOMAIN, config)

        self.hass.states.set(TEST_ENTITY, STATE_ON)
        self.hass.block_till_done()
        self.assertEqual(1, len(events))
        last_event = events[-1]
        self.assertEqual(last_event.data[notify.ATTR_DATA], TEST_DATA)

    def test_skipfirst(self):
        """Test skipping first notification."""
        config = deepcopy(TEST_CONFIG)
        config[alert.DOMAIN][NAME][alert.CONF_SKIP_FIRST] = True
        events = []

        @callback
        def record_event(event):
            """Add recorded event to set."""
            events.append(event)

        self.hass.services.register(notify.DOMAIN, NOTIFIER, record_event)

        assert setup_component(self.hass, alert.DOMAIN, config)
        assert len(events) == 0

        self.hass.states.set("sensor.test", STATE_ON)
        self.hass.block_till_done()
        assert len(events) == 0

    def test_noack(self):
        """Test no ack feature."""
        entity = alert.Alert(self.hass, *TEST_NOACK)
        self.hass.add_job(entity.begin_alerting)
        self.hass.block_till_done()

        assert entity.hidden is True

    def test_done_message_state_tracker_reset_on_cancel(self):
        """Test that the done message is reset when canceled."""
        entity = alert.Alert(self.hass, *TEST_NOACK)
        entity._cancel = lambda *args: None
        assert entity._send_done_message is False
        entity._send_done_message = True
        self.hass.add_job(entity.end_alerting)
        self.hass.block_till_done()
        assert entity._send_done_message is False
