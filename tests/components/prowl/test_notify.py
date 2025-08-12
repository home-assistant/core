"""Test the Prowl notifications."""

import prowlpy
import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_API_KEY


async def test_send_notification_service(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_prowlpy
) -> None:
    """Set up Prowl, call notify service, and check API call."""
    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        {
            "message": "Test Notification",
            "title": "Test Title",
        },
        blocking=True,
    )

    assert mock_prowlpy.send.call_count > 0


async def test_fail_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_prowlpy
) -> None:
    """Sending a message via Prowl with a failure."""
    mock_prowlpy.send.side_effect = prowlpy.APIError("Internal server error")

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            {
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_prowlpy.send.call_count > 0


async def test_send_notification_timeout(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_prowlpy
) -> None:
    """Sending a message via Prowl with a timeout."""
    mock_prowlpy.send.side_effect = TimeoutError

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(TimeoutError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            {
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_prowlpy.send.call_count > 0


async def test_forbidden_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_prowlpy
) -> None:
    """Sending a message via Prowl with a forbidden error."""
    mock_prowlpy.send.side_effect = prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}")

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(ConfigEntryAuthFailed):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            {
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_prowlpy.send.call_count > 0


async def test_rate_limited_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_prowlpy
) -> None:
    """Sending a message via Prowl with a forbidden error."""
    mock_prowlpy.send.side_effect = prowlpy.APIError(
        "Not accepted: Your IP address has exceeded the API limit"
    )

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(ConfigEntryAuthFailed):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            {
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_prowlpy.send.call_count > 0


async def test_other_exception_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_prowlpy
) -> None:
    """Sending a message via Prowl with a general unhandled exception."""
    mock_prowlpy.send.side_effect = SyntaxError

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(SyntaxError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            {
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_prowlpy.send.call_count > 0
