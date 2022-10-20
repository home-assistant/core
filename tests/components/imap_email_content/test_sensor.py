"""The tests for the IMAP email content sensor platform."""
import base64
from collections import deque
import datetime
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from homeassistant.components.imap_email_content import sensor as imap_email_content
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.template import Template


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


async def test_allowed_sender(hass):
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


async def test_multi_part_with_text(hass):
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


async def test_multi_part_only_html(hass):
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


async def test_multi_part_only_other_text(hass):
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


async def test_multi_part_with_text_and_html_base64_encoded_return_text_part(hass):
    """
    Test with multi part emails with text and html encoded in base64.

    The sensor body will be the original text part.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    text = "Test Message ✉"
    html = "<html><head></head><body>Test Message ✉</body></html>"

    # with utf-8 charset, MIMEText créate an base64 encoded body
    textPart = MIMEText(text, "plain", _charset="utf-8")
    htmlPart = MIMEText(html, "html", _charset="utf-8")
    assert textPart.get("Content-Transfer-Encoding") == "base64"
    assert htmlPart.get("Content-Transfer-Encoding") == "base64"

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
    assert sensor.extra_state_attributes["body"] == text


async def test_multi_part_only_html_base64_encoded(hass):
    """
    Test with multi part emails with only HTML encoded in base64.

    The sensor body will be the original html part.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    html = "<html><head></head><body>Test Message ✉</body></html>"

    # with utf-8 charset, MIMEText créate an base64 encoded body
    htmlPart = MIMEText(html, "html", _charset="utf-8")
    assert htmlPart.get("Content-Transfer-Encoding") == "base64"

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
    assert sensor.extra_state_attributes["body"] == html


async def test_multi_part_only_untyped_text_base64_encoded(hass):
    """
    Test with multi part emails with only untyped text encoded in base64.

    The sensor body will be the untyped part.

    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    untyped = "Test Message ✉"

    # with utf-8 charset, MIMEText créate an base64 encoded body
    htmlPart = MIMEText(untyped, "text", _charset="utf-8")
    assert htmlPart.get("Content-Transfer-Encoding") == "base64"

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
    assert sensor.extra_state_attributes["body"] == untyped


async def test_multi_part_only_plain_text_without_Content_Transfer_Encoding(hass):
    """
    Test with multi part emails with text encoded in base64, but without header Content-Transfer-Encoding.

    The sensor body will be the text encoded in base64.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    text = "Test Message ✉"

    # with utf-8 charset, MIMEText créate an base64 encoded body
    htmlPart = MIMEText(text, "text", _charset="utf-8")
    # remove the Content-Transfer-Encoding header
    htmlPart.__delitem__("Content-Transfer-Encoding")

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
    # email content not properly decoded, body steel in base64
    assert (
        sensor.extra_state_attributes["body"]
        == base64.standard_b64encode(text.encode()).decode("utf-8") + "\n"
    )


async def test_multi_part_with_text_quoted_printable_encoded(hass):
    """
    Test with multi part emails with text and html encoded in quoted-printable.

    The sensor body will be the original text part.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Link"
    msg["From"] = "sender@test.com"

    text = "Test Message ✉"
    html = "<html><head></head><body>Test Message ✉</body></html>"

    textPart = MIMEText("", "plain")
    htmlPart = MIMEText("", "html")
    textPart.replace_header("content-transfer-encoding", "quoted-printable")
    htmlPart.replace_header("content-transfer-encoding", "quoted-printable")
    textPart.set_payload(text, "utf-8")
    htmlPart.set_payload(html, "utf-8")

    assert textPart.get("Content-Transfer-Encoding") == "quoted-printable"
    assert htmlPart.get("Content-Transfer-Encoding") == "quoted-printable"

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
    assert sensor.extra_state_attributes["body"] == text


async def test_multiple_emails(hass):
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


async def test_sender_not_allowed(hass):
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


async def test_template(hass):
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
