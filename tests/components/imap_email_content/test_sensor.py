"""The tests for the IMAP email content sensor platform."""
from collections import deque
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import datetime
import unittest

from homeassistant.helpers.template import Template
from homeassistant.helpers.event import track_state_change
from homeassistant.components.imap_email_content \
    import sensor as imap_email_content

from tests.common import get_test_home_assistant


class FakeEMailReader:
    """A test class for sending test emails."""

    def __init__(self, messages):
        """Set up the fake email reader."""
        self._messages = messages

    def connect(self):
        """Stay always Connected."""
        return True

    def read_next(self):
        """Get the next email."""
        if len(self._messages) == 0:
            return None
        return self._messages.popleft()


class EmailContentSensor(unittest.TestCase):
    """Test the IMAP email content sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_allowed_sender(self):
        """Test emails from allowed sender."""
        test_message = email.message.Message()
        test_message['From'] = 'sender@test.com'
        test_message['Subject'] = 'Test'
        test_message['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message.set_payload("Test Message")

        sensor = imap_email_content.EmailContentSensor(
            self.hass,
            FakeEMailReader(deque([test_message])),
            "test_emails_sensor",
            ["sender@test.com"],
            None)

        sensor.entity_id = 'sensor.emailtest'
        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert 'Test' == sensor.state
        assert "Test Message" == \
            sensor.device_state_attributes['body']
        assert 'sender@test.com' == \
            sensor.device_state_attributes['from']
        assert 'Test' == sensor.device_state_attributes['subject']
        assert datetime.datetime(2016, 1, 1, 12, 44, 57) == \
            sensor.device_state_attributes['date']

    def test_multi_part_with_text(self):
        """Test multi part emails."""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Link'
        msg['From'] = 'sender@test.com'

        text = "Test Message"
        html = "<html><head></head><body>Test Message</body></html>"

        textPart = MIMEText(text, 'plain')
        htmlPart = MIMEText(html, 'html')

        msg.attach(textPart)
        msg.attach(htmlPart)

        sensor = imap_email_content.EmailContentSensor(
            self.hass,  FakeEMailReader(deque([msg])), 'test_emails_sensor',
            ['sender@test.com'], None)

        sensor.entity_id = "sensor.emailtest"
        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert 'Link' == sensor.state
        assert "Test Message" == \
            sensor.device_state_attributes['body']

    def test_multi_part_only_html(self):
        """Test multi part emails with only HTML."""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Link'
        msg['From'] = 'sender@test.com'

        html = "<html><head></head><body>Test Message</body></html>"

        htmlPart = MIMEText(html, 'html')

        msg.attach(htmlPart)

        sensor = imap_email_content.EmailContentSensor(
            self.hass,
            FakeEMailReader(deque([msg])),
            'test_emails_sensor',
            ['sender@test.com'],
            None)

        sensor.entity_id = 'sensor.emailtest'
        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert 'Link' == sensor.state
        assert "<html><head></head><body>Test Message</body></html>" == \
            sensor.device_state_attributes['body']

    def test_multi_part_only_other_text(self):
        """Test multi part emails with only other text."""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Link'
        msg['From'] = 'sender@test.com'

        other = "Test Message"

        htmlPart = MIMEText(other, 'other')

        msg.attach(htmlPart)

        sensor = imap_email_content.EmailContentSensor(
            self.hass, FakeEMailReader(deque([msg])), 'test_emails_sensor',
            ['sender@test.com'], None)

        sensor.entity_id = 'sensor.emailtest'
        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert 'Link' == sensor.state
        assert "Test Message" == \
            sensor.device_state_attributes['body']

    def test_multiple_emails(self):
        """Test multiple emails."""
        states = []

        test_message1 = email.message.Message()
        test_message1['From'] = 'sender@test.com'
        test_message1['Subject'] = 'Test'
        test_message1['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message1.set_payload("Test Message")

        test_message2 = email.message.Message()
        test_message2['From'] = 'sender@test.com'
        test_message2['Subject'] = 'Test 2'
        test_message2['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message2.set_payload("Test Message 2")

        def state_changed_listener(entity_id, from_s, to_s):
            states.append(to_s)

        track_state_change(
            self.hass, ['sensor.emailtest'], state_changed_listener)

        sensor = imap_email_content.EmailContentSensor(
            self.hass,
            FakeEMailReader(deque([test_message1, test_message2])),
            'test_emails_sensor', ['sender@test.com'], None)

        sensor.entity_id = 'sensor.emailtest'

        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()
        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()

        assert "Test" == states[0].state
        assert "Test 2" == states[1].state

        assert "Test Message 2" == \
            sensor.device_state_attributes['body']

    def test_sender_not_allowed(self):
        """Test not whitelisted emails."""
        test_message = email.message.Message()
        test_message['From'] = 'sender@test.com'
        test_message['Subject'] = 'Test'
        test_message['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message.set_payload("Test Message")

        sensor = imap_email_content.EmailContentSensor(
            self.hass, FakeEMailReader(deque([test_message])),
            'test_emails_sensor', ['other@test.com'], None)

        sensor.entity_id = 'sensor.emailtest'
        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert sensor.state is None

    def test_template(self):
        """Test value template."""
        test_message = email.message.Message()
        test_message['From'] = 'sender@test.com'
        test_message['Subject'] = 'Test'
        test_message['Date'] = datetime.datetime(2016, 1, 1, 12, 44, 57)
        test_message.set_payload("Test Message")

        sensor = imap_email_content.EmailContentSensor(
            self.hass, FakeEMailReader(deque([test_message])),
            'test_emails_sensor', ['sender@test.com'],
            Template("{{ subject }} from {{ from }} with message {{ body }}",
                     self.hass))

        sensor.entity_id = 'sensor.emailtest'
        sensor.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert "Test from sender@test.com with message Test Message" == \
            sensor.state
