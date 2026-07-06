"""The tests for the notify smtp platform."""

from pathlib import Path
import re
from smtplib import (
    SMTPAuthenticationError,
    SMTPHeloError,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)
from socket import gaierror
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.smtp.const import (
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DOMAIN,
)
from homeassistant.components.smtp.notify import MailNotificationService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.ssl import create_client_context

from tests.common import MockConfigEntry, snapshot_platform


class MockSMTP(MailNotificationService):
    """Test SMTP object that doesn't need a working server."""

    def _send_email(self, msg, recipients):
        """Just return msg string and recipients for testing."""
        return msg.as_string(), recipients


@pytest.fixture
def message():
    """Return MockSMTP object with test data."""
    return MockSMTP(
        config={
            CONF_SERVER: "localhost",
            CONF_PORT: 25,
            CONF_TIMEOUT: 5,
            CONF_SENDER: "test@test.com",
            CONF_ENCRYPTION: 1,
            CONF_USERNAME: "testuser",
            CONF_PASSWORD: "testpass",
            CONF_RECIPIENT: ["recip1@example.com", "testrecip@test.com"],
            CONF_SENDER_NAME: "Home Assistant",
            CONF_VERIFY_SSL: True,
        },
        ssl_context=create_client_context(),
    )


HTML = """
        <!DOCTYPE html>
        <html lang="en" xmlns="http://www.w3.org/1999/xhtml">
            <head><meta charset="UTF-8"></head>
            <body>
              <div>
                <h1>Intruder alert at apartment!!</h1>
              </div>
              <div>
                <img alt="tests/testing_config/notify/test.jpg"\
 src="cid:tests/testing_config/notify/test.jpg"/>
              </div>
            </body>
        </html>"""


EMAIL_DATA = [
    (
        "Test msg",
        {"images": ["tests/testing_config/notify/test.jpg"]},
        "Content-Type: multipart/mixed",
    ),
    (
        "Test msg",
        {"html": HTML, "images": ["tests/testing_config/notify/test.jpg"]},
        "Content-Type: multipart/related",
    ),
    (
        "Test msg",
        {"html": HTML, "images": ["tests/testing_config/notify/test_not_exists.jpg"]},
        "Content-Type: multipart/related",
    ),
    (
        "Test msg",
        {"html": HTML, "images": ["tests/testing_config/notify/test.pdf"]},
        "Content-Type: multipart/related",
    ),
]


@pytest.mark.parametrize(
    ("message_data", "data", "content_type"),
    EMAIL_DATA,
    ids=[
        "Tests when sending text message and images.",
        "Tests when sending text message, HTML Template and images.",
        "Tests when image does not exist at mentioned location.",
        "Tests when image type cannot be detected or is of wrong type.",
    ],
)
def test_send_message(
    hass: HomeAssistant, message_data, data, content_type, message
) -> None:
    """Verify if we can send messages of all types correctly."""
    sample_email = "<mock@mock>"
    message.hass = hass
    hass.config.allowlist_external_dirs.add(Path("tests/testing_config").resolve())
    with patch("email.utils.make_msgid", return_value=sample_email):
        result, _ = message.send_message(message_data, data=data)
        assert content_type in result


@pytest.mark.parametrize(
    ("message_data", "data", "content_type"),
    [
        (
            "Test msg",
            {"images": ["tests/testing_config/notify/test.jpg"]},
            "Content-Type: multipart/mixed",
        ),
    ],
)
def test_sending_insecure_files_fails(
    hass: HomeAssistant,
    message_data,
    data,
    content_type,
    message,
) -> None:
    """Verify if we cannot send messages with insecure attachments."""
    sample_email = "<mock@mock>"
    message.hass = hass
    with (
        patch("email.utils.make_msgid", return_value=sample_email),
        pytest.raises(ServiceValidationError) as exc,
    ):
        _result, _ = message.send_message(message_data, data=data)
    assert exc.value.translation_key == "remote_path_not_allowed"
    assert exc.value.translation_domain == DOMAIN
    assert (
        str(exc.value.translation_placeholders["file_path"])
        == "tests/testing_config/notify"
    )
    assert exc.value.translation_placeholders["url"]
    assert exc.value.translation_placeholders["file_name"] == "test.jpg"


def test_send_text_message(hass: HomeAssistant, message) -> None:
    """Verify if we can send simple text message."""
    expected = (
        '^Content-Type: text/plain; charset="us-ascii"\n'
        "MIME-Version: 1.0\n"
        "Content-Transfer-Encoding: 7bit\n"
        "Subject: Home Assistant\n"
        "To: recip1@example.com,testrecip@test.com\n"
        "From: Home Assistant <test@test.com>\n"
        "X-Mailer: Home Assistant\n"
        "Date: [^\n]+\n"
        "Message-Id: <[^@]+@[^>]+>\n"
        "\n"
        "Test msg$"
    )
    sample_email = "<mock@mock>"
    message_data = "Test msg"
    with patch("email.utils.make_msgid", return_value=sample_email):
        result, _ = message.send_message(message_data)
        assert re.search(expected, result)


@pytest.mark.parametrize(
    "target",
    [
        None,
        "target@example.com",
    ],
    ids=[
        "Verify we can send email to default recipient.",
        "Verify email recipient can be overwritten by target arg.",
    ],
)
def test_send_target_message(target, hass: HomeAssistant, message) -> None:
    """Verify if we can send email to correct recipient."""
    sample_email = "<mock@mock>"
    message_data = "Test msg"
    with patch("email.utils.make_msgid", return_value=sample_email):
        if not target:
            expected_recipient = ["recip1@example.com", "testrecip@test.com"]
        else:
            expected_recipient = target

        _, recipient = message.send_message(message_data, target=target)
        assert recipient == expected_recipient


@pytest.mark.usefixtures("smtp")
async def test_notify_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the SMTP notify platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("make_msgid")
@pytest.mark.freeze_time("2026-05-03T03:09:37+00:00")
async def test_notify_send_message(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    smtp: MagicMock,
) -> None:
    """Test sending an email message via notify.send_message action."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("notify.home_assistant_recipient")
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.home_assistant_recipient",
            ATTR_MESSAGE: "Hello World",
        },
        blocking=True,
    )

    state = hass.states.get("notify.home_assistant_recipient")
    assert state
    assert state.state == "2026-05-03T03:09:37+00:00"

    smtp.sendmail.assert_called_once_with(
        "email@example.com",
        "recipient@example.com",
        (
            'Content-Type: text/plain; charset="us-ascii"\n'
            "MIME-Version: 1.0\n"
            "Content-Transfer-Encoding: 7bit\n"
            "Subject: Home Assistant\n"
            "From: Home Assistant <email@example.com>\n"
            "To: Recipient <recipient@example.com>\n"
            "X-Mailer: Home Assistant\n"
            "Date: Sat, 02 May 2026 20:09:37 -0700\n"
            "Message-Id: <177777777700.12345.12345678901234567890@mock>\n\n"
            "Hello World"
        ),
    )


@pytest.mark.parametrize(
    ("call_method", "exception", "translation_key"),
    [
        ("login", SMTPAuthenticationError(0, ""), "authentication_error"),
        ("login", gaierror, "send_mail_connection_error"),
        ("login", ConnectionRefusedError, "send_mail_connection_error"),
        ("login", SMTPHeloError(0, ""), "send_mail_connection_error"),
        ("sendmail", SMTPServerDisconnected, "send_mail_connection_error"),
        ("sendmail", SMTPSenderRefused(0, b"", ""), "send_mail_connection_error"),
    ],
)
@pytest.mark.freeze_time("2026-05-03T03:09:37+00:00")
async def test_notify_send_message_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    smtp: MagicMock,
    call_method: str,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test exceptions via notify.send_message action."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    getattr(smtp, call_method).side_effect = exception

    with pytest.raises(HomeAssistantError) as e:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_ENTITY_ID: "notify.home_assistant_recipient",
                ATTR_MESSAGE: "Hello World",
            },
            blocking=True,
        )

    assert e.value.translation_key == translation_key


@pytest.mark.usefixtures("make_msgid")
@pytest.mark.freeze_time("2026-05-03T03:09:37+00:00")
async def test_notify_retry_on_disconnect_with_broken_quit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    smtp: MagicMock,
) -> None:
    """Test retry succeeds when quit() raises on a dead connection."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    smtp.sendmail.side_effect = [SMTPServerDisconnected("gone"), None]
    smtp.quit.side_effect = SMTPServerDisconnected("please run connect() first")

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_ENTITY_ID: "notify.home_assistant_recipient",
            ATTR_MESSAGE: "Hello World",
        },
        blocking=True,
    )

    assert smtp.sendmail.call_count == 2
