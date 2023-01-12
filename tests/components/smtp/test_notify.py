"""The tests for the notify smtp platform."""
import smtplib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import notify
from homeassistant.components.smtp.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import get_repairs
from tests.components.smtp import MOCK_CONFIG, MOCK_USER_INPUT


@pytest.fixture(autouse=True)
def mock_client():
    """Return mock smtp client."""
    with patch("email.utils.make_msgid", return_value="<mock@mock>"), patch(
        "homeassistant.components.smtp.get_smtp_client"
    ) as mock_client:
        mock_client.return_value.sendmail.return_value = {}
        mock_client.return_value.quit.return_value = ()
        yield mock_client


HTML = """
        <!DOCTYPE html>
        <html lang="en" xmlns="http://www.w3.org/1999/xhtml">
            <head><meta charset="UTF-8"></head>
            <body>
              <div>
                <h1>Intruder alert at apartment!!</h1>
              </div>
              <div>
                <img alt="tests/testing_config/notify/test.jpg" src="cid:tests/testing_config/notify/test.jpg"/>
              </div>
            </body>
        </html>"""


EMAIL_DATA = [
    ("Test msg", {}),
    (
        "Test msg",
        {"images": ["tests/testing_config/notify/test.jpg"]},
    ),
    (
        "Test msg",
        {"html": HTML, "images": ["tests/testing_config/notify/test.jpg"]},
    ),
    (
        "Test msg",
        {"html": HTML, "images": ["tests/testing_config/notify/test.pdf"]},
    ),
]


async def test_setup_notify(hass: HomeAssistant, hass_ws_client) -> None:
    """Test setting up notify with no discovery info."""
    assert await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {"platform": "smtp", **MOCK_CONFIG},
            ]
        },
    )
    await hass.async_block_till_done()

    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "deprecated_yaml"

    assert notify.DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "message, data",
    EMAIL_DATA,
    ids=[
        "Tests when sending plain text message.",
        "Tests when sending text message and images.",
        "Tests when sending text message, HTML Template and images.",
        "Tests when image type cannot be detected or is of wrong type.",
    ],
)
async def test_send_message(hass: HomeAssistant, message: str, data: dict[str, Any]):
    """Verify if we can send messages of all types correctly."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    print(mock_client)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_data = {
        notify.ATTR_MESSAGE: message,
        notify.ATTR_TARGET: ["sample@mail.com"],
        notify.ATTR_DATA: data,
    }
    assert await hass.services.async_call(
        notify.DOMAIN, "smtp", service_data, blocking=True
    )


async def test_missing_target(hass: HomeAssistant, hass_ws_client) -> None:
    """Test that we raise an issue if recipients are missing."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_data = {
        notify.ATTR_MESSAGE: "Test message",
    }
    with pytest.raises(ValueError):
        assert await hass.services.async_call(
            notify.DOMAIN, "smtp", service_data, blocking=True
        )
    issues = await get_repairs(hass, hass_ws_client)
    assert len(issues) == 1
    assert issues[0]["issue_id"] == "missing_target"


async def test_invalid_target(hass: HomeAssistant, hass_ws_client) -> None:
    """Test that we raise an error if target is not a valid email address."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_data = {
        notify.ATTR_MESSAGE: "Test message",
        notify.ATTR_TARGET: "not_an_email",
    }
    with pytest.raises(ValueError):
        await hass.services.async_call(
            notify.DOMAIN, "smtp", service_data, blocking=True
        )


async def test_attachment_not_found(hass: HomeAssistant):
    """Test an error is raised if attachment is not found."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    print(mock_client)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_data = {
        notify.ATTR_MESSAGE: "test message",
        notify.ATTR_TARGET: ["sample@mail.com"],
        notify.ATTR_DATA: {"images": ["invalid_file.jpg"]},
    }
    with pytest.raises(ValueError) as err:
        await hass.services.async_call(
            notify.DOMAIN, "smtp", service_data, blocking=True
        )
    assert str(err.value) == "Attachment invalid_file.jpg not found."


async def test_fail_sending_mail(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test failing to send the email due to connection error."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_data = {
        notify.ATTR_MESSAGE: "Test message",
        notify.ATTR_TARGET: "example@mail.com",
    }
    mock_client.return_value.sendmail.side_effect = [
        smtplib.SMTPException,
        smtplib.SMTPException,
    ]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            notify.DOMAIN, "smtp", service_data, blocking=True
        )


async def test_sendmail_second_attempt(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test mail is sent on second attempt."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_data = {
        notify.ATTR_MESSAGE: "Test message",
        notify.ATTR_TARGET: "example@mail.com",
    }
    mock_client.return_value.sendmail.side_effect = [smtplib.SMTPException, {}]
    assert await hass.services.async_call(
        notify.DOMAIN, "smtp", service_data, blocking=True
    )
