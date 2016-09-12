"""The tests for the Command line sensor platform."""
import unittest
import email
import datetime

from homeassistant.helpers.event import track_state_change
from collections import deque

from homeassistant.components.sensor import email as email_component
from tests.common import get_test_home_assistant


class FakeEMailReader:
    def __init__(self, messages):
        self._messages = messages

    def connect(self):
        return True

    def read_next(self):
        if len(self._messages) == 0:
            return None
        return self._messages.popleft()


class TestEMail(unittest.TestCase):
    """Test the Command line sensor."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_allowed_sender(self):
        test_message = email.message.Message()
        test_message['From'] = "sender@test.com"
        test_message['Subject'] = "Test"
        test_message['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message.set_payload("Test Message")

        sensor = email_component.EmailSensor(
            self.hass,
            FakeEMailReader(deque([test_message])),
            "test_emails_sensor",
            ["sender@test.com"],
            None)

        sensor.entity_id = "sensor.emailtest"
        sensor.update()
        self.assertEqual("Test Message", sensor.state)

    def test_multiple_emails(self):
        states = []

        test_message1 = email.message.Message()
        test_message1['From'] = "sender@test.com"
        test_message1['Subject'] = "Test"
        test_message1['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message1.set_payload("Test Message")

        test_message2 = email.message.Message()
        test_message2['From'] = "sender@test.com"
        test_message2['Subject'] = "Test 2"
        test_message2['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message2.set_payload("Test Message 2")

        def state_changed_listener(entity_id, from_s, to_s):
            states.append(to_s)

        track_state_change(
            self.hass,
            ["sensor.emailtest"],
            state_changed_listener)

        sensor = email_component.EmailSensor(
            self.hass,
            FakeEMailReader(deque([test_message1, test_message2])),
            "test_emails_sensor",
            ["sender@test.com"],
            None)

        sensor.entity_id = "sensor.emailtest"
        sensor.update()

        self.hass.pool.block_till_done()

        self.assertEqual("Test Message", states[0].state)
        self.assertEqual("Test Message 2", states[1].state)

        self.assertEqual("Test Message 2", sensor.state)

    def test_sender_not_allowed(self):
        test_message = email.message.Message()
        test_message['From'] = "sender@test.com"
        test_message['Subject'] = "Test"
        test_message['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message.set_payload("Test Message")

        sensor = email_component.EmailSensor(
            self.hass,
            FakeEMailReader(deque([test_message])),
            "test_emails_sensor",
            ["other@test.com"],
            None)

        sensor.entity_id = "sensor.emailtest"
        sensor.update()
        self.assertEqual(None, sensor.state)

    def test_template(self):
        test_message = email.message.Message()
        test_message['From'] = "sender@test.com"
        test_message['Subject'] = "Test"
        test_message['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message.set_payload("Test Message")

        sensor = email_component.EmailSensor(
            self.hass,
            FakeEMailReader(deque([test_message])),
            "test_emails_sensor",
            ["sender@test.com"],
            "email from {{ from }} with message {{ body }}")

        sensor.entity_id = "sensor.emailtest"
        sensor.update()
        self.assertEqual(
            "email from sender@test.com with message Test Message",
            sensor.state)
