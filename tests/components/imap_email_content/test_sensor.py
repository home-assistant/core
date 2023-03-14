"""The tests for the IMAP email content sensor platform."""
from collections import deque
import datetime
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock

from homeassistant.components.imap_email_content import sensor as imap_email_content
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component

from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry


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


async def test_allowed_sender(hass: HomeAssistant) -> None:
    """Test emails from allowed sender."""
    test_message = email.message.Message()
    test_message["From"] = "sender@test.com"
    test_message["Subject"] = "Test"
    test_message["Date"] = datetime.datetime(2016, 1, 1, 12, 44, 57)
    test_message.set_payload("Test Message")

    sensor = imap_email_content.EmailContentSensor(
        hass,
        FakeEMailReader(deque([test_message])),
        "test_emails_sensor",
        ["sender@test.com"],
        None,
    )

    sensor.entity_id = "sensor.emailtest"
    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert sensor.state == "Test"
    assert sensor.extra_state_attributes["body"] == "Test Message"
    assert sensor.extra_state_attributes["from"] == "sender@test.com"
    assert sensor.extra_state_attributes["subject"] == "Test"
    assert (
        datetime.datetime(2016, 1, 1, 12, 44, 57)
        == sensor.extra_state_attributes["date"]
    )


async def test_multi_part_with_text(hass: HomeAssistant) -> None:
    """Test multi part emails."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    text = "Test Message"
    html = "<html><head></head><body>Test Message</body></html>"

    textPart = MIMEText(text, "plain")
    htmlPart = MIMEText(html, "html")

    msg.attach(textPart)
    msg.attach(htmlPart)

    sensor = imap_email_content.EmailContentSensor(
        hass,
        FakeEMailReader(deque([msg])),
        "test_emails_sensor",
        ["sender@test.com"],
        None,
    )

    sensor.entity_id = "sensor.emailtest"
    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert sensor.state == "Link"
    assert sensor.extra_state_attributes["body"] == "Test Message"


async def test_multi_part_only_html(hass: HomeAssistant) -> None:
    """Test multi part emails with only HTML."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    html = "<html><head></head><body>Test Message</body></html>"

    htmlPart = MIMEText(html, "html")

    msg.attach(htmlPart)

    sensor = imap_email_content.EmailContentSensor(
        hass,
        FakeEMailReader(deque([msg])),
        "test_emails_sensor",
        ["sender@test.com"],
        None,
    )

    sensor.entity_id = "sensor.emailtest"
    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert sensor.state == "Link"
    assert (
        sensor.extra_state_attributes["body"]
        == "<html><head></head><body>Test Message</body></html>"
    )


async def test_multi_part_only_other_text(hass: HomeAssistant) -> None:
    """Test multi part emails with only other text."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    other = "Test Message"

    htmlPart = MIMEText(other, "other")

    msg.attach(htmlPart)

    sensor = imap_email_content.EmailContentSensor(
        hass,
        FakeEMailReader(deque([msg])),
        "test_emails_sensor",
        ["sender@test.com"],
        None,
    )

    sensor.entity_id = "sensor.emailtest"
    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert sensor.state == "Link"
    assert sensor.extra_state_attributes["body"] == "Test Message"


async def test_multiple_emails(hass: HomeAssistant) -> None:
    """Test multiple emails."""
    states = []

    test_message1 = email.message.Message()
    test_message1["From"] = "sender@test.com"
    test_message1["Subject"] = "Test"
    test_message1["Date"] = datetime.datetime(2016, 1, 1, 12, 44, 57)
    test_message1.set_payload("Test Message")

    test_message2 = email.message.Message()
    test_message2["From"] = "sender@test.com"
    test_message2["Subject"] = "Test 2"
    test_message2["Date"] = datetime.datetime(2016, 1, 1, 12, 44, 57)
    test_message2.set_payload("Test Message 2")

    def state_changed_listener(entity_id, from_s, to_s):
        states.append(to_s)

    async_track_state_change(hass, ["sensor.emailtest"], state_changed_listener)

    sensor = imap_email_content.EmailContentSensor(
        hass,
        FakeEMailReader(deque([test_message1, test_message2])),
        "test_emails_sensor",
        ["sender@test.com"],
        None,
    )

    sensor.entity_id = "sensor.emailtest"

    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()
    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()

    assert states[0].state == "Test"
    assert states[1].state == "Test 2"

    assert sensor.extra_state_attributes["body"] == "Test Message 2"


async def test_sender_not_allowed(hass: HomeAssistant) -> None:
    """Test not whitelisted emails."""
    test_message = email.message.Message()
    test_message["From"] = "sender@test.com"
    test_message["Subject"] = "Test"
    test_message["Date"] = datetime.datetime(2016, 1, 1, 12, 44, 57)
    test_message.set_payload("Test Message")

    sensor = imap_email_content.EmailContentSensor(
        hass,
        FakeEMailReader(deque([test_message])),
        "test_emails_sensor",
        ["other@test.com"],
        None,
    )

    sensor.entity_id = "sensor.emailtest"
    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert sensor.state is None


async def test_template(hass: HomeAssistant) -> None:
    """Test value template."""
    test_message = email.message.Message()
    test_message["From"] = "sender@test.com"
    test_message["Subject"] = "Test"
    test_message["Date"] = datetime.datetime(2016, 1, 1, 12, 44, 57)
    test_message.set_payload("Test Message")

    sensor = imap_email_content.EmailContentSensor(
        hass,
        FakeEMailReader(deque([test_message])),
        "test_emails_sensor",
        ["sender@test.com"],
        Template("{{ subject }} from {{ from }} with message {{ body }}", hass),
    )

    sensor.entity_id = "sensor.emailtest"
    sensor.async_schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert sensor.state == "Test from sender@test.com with message Test Message"


async def test_component_setup_and_migration(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test setup from configuration.yaml and migration to entry."""
    mock_client.connect.return_value = True
    config = MOCK_CONFIG.copy()
    config[CONF_PLATFORM] = imap_email_content.DOMAIN
    assert await async_setup_component(hass, "sensor", {"sensor": config})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(imap_email_content.DOMAIN)
    entry = entries[0]
    assert entry.data == MOCK_CONFIG


async def test_migration_happens_once(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test skipping migration to entry."""

    # Set up entry of previously imported yaml config
    entry = MockConfigEntry(
        domain=imap_email_content.DOMAIN, data=MOCK_CONFIG, title="email_email_com"
    )
    entry.add_to_hass(hass)

    mock_client.connect.return_value = True
    config = MOCK_CONFIG.copy()
    config[CONF_PLATFORM] = imap_email_content.DOMAIN

    assert await async_setup_component(hass, "sensor", {"sensor": [config]})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(imap_email_content.DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.data == MOCK_CONFIG
