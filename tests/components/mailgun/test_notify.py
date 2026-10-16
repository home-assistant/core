"""Test Mailgun notifications."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from pymailgunner import MailgunCredentialsError, MailgunDomainError, MailgunError
import pytest

from homeassistant.components.mailgun.const import DOMAIN
from homeassistant.components.mailgun.notify import MailgunNotificationService
from homeassistant.components.notify import ATTR_TITLE_DEFAULT, DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DOMAIN,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_RECIPIENT,
    CONF_SENDER,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

SERVICE_NAME = "mailgun"


@pytest.fixture
def mock_client_class() -> Generator[MagicMock]:
    """Mock the pymailgunner client class."""
    with patch(
        "homeassistant.components.mailgun.notify.Client", autospec=True
    ) as mock_class:
        mock_class.return_value.domain = "example.com"
        yield mock_class


@pytest.fixture
def mock_client(mock_client_class: MagicMock) -> MagicMock:
    """Return the mocked pymailgunner client."""
    return mock_client_class.return_value


async def setup_notify_platform(hass: HomeAssistant) -> None:
    """Set up the Mailgun component and the legacy notify platform."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_API_KEY: "api-key", CONF_DOMAIN: "example.com"}},
    )
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: {
                CONF_NAME: SERVICE_NAME,
                CONF_PLATFORM: DOMAIN,
                CONF_RECIPIENT: "recipient@example.com",
                CONF_SENDER: "sender@example.com",
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("service_data", "expected_subject", "expected_files"),
    [
        pytest.param({}, ATTR_TITLE_DEFAULT, None, id="message_only"),
        pytest.param({"title": "Test"}, "Test", None, id="with_title"),
        pytest.param(
            {"data": {"images": ["image.jpg"]}},
            ATTR_TITLE_DEFAULT,
            ["image.jpg"],
            id="with_images",
        ),
    ],
)
async def test_send_message(
    hass: HomeAssistant,
    mock_client: MagicMock,
    service_data: dict[str, Any],
    expected_subject: str,
    expected_files: list[str] | None,
) -> None:
    """Test sending a message."""
    await setup_notify_platform(hass)
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        {"message": "Hello", **service_data},
        blocking=True,
    )

    mock_client.send_mail.assert_called_once_with(
        sender="sender@example.com",
        to="recipient@example.com",
        subject=expected_subject,
        text="Hello",
        files=expected_files,
    )


def test_send_message_initializes_client(mock_client: MagicMock) -> None:
    """Test that send_message initializes a missing client and derives the sender.

    This bypasses the registered service because the lazy initialization branch
    is unreachable through it: get_service always calls connection_is_valid,
    which already initializes the client.
    """
    service = MailgunNotificationService(
        "example.com", False, "api-key", None, "recipient@example.com"
    )

    service.send_message("Hello")

    mock_client.send_mail.assert_called_once_with(
        sender="hass@example.com",
        to="recipient@example.com",
        subject=ATTR_TITLE_DEFAULT,
        text="Hello",
        files=None,
    )


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(MailgunError, id="base_error"),
        pytest.param(MailgunCredentialsError, id="credentials_error"),
        pytest.param(MailgunDomainError, id="domain_error"),
    ],
)
async def test_send_message_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: type[MailgunError],
) -> None:
    """Test that a failing send raises an error with a translation key."""
    await setup_notify_platform(hass)
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)
    mock_client.send_mail.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_NAME,
            {"message": "Hello"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "send_message_failed"


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(MailgunCredentialsError, id="invalid_credentials"),
        pytest.param(MailgunDomainError, id="invalid_domain"),
    ],
)
async def test_setup_with_connection_error(
    hass: HomeAssistant,
    mock_client_class: MagicMock,
    side_effect: type[MailgunError],
) -> None:
    """Test that the notify service is not created when the connection fails."""
    mock_client_class.side_effect = side_effect

    await setup_notify_platform(hass)

    assert not hass.services.has_service(NOTIFY_DOMAIN, SERVICE_NAME)
