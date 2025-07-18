"""Test the Prowl notifications."""

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_send_notification_service(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_pyprowl
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

    assert mock_pyprowl.notify.call_count > 0


async def test_fail_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_pyprowl
) -> None:
    """Sending a message via Prowl with a failure."""
    mock_pyprowl.notify.side_effect = Exception("500 Error")

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

    assert mock_pyprowl.notify.call_count > 0


async def test_send_notification_timeout(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_pyprowl
) -> None:
    """Sending a message via Prowl with a timeout."""
    mock_pyprowl.notify.side_effect = TimeoutError

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

    assert mock_pyprowl.notify.call_count > 0


async def test_forbidden_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_pyprowl
) -> None:
    """Sending a message via Prowl with a forbidden error."""
    mock_pyprowl.notify.side_effect = Exception("401 Access Denied")

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

    assert mock_pyprowl.notify.call_count > 0


async def test_other_exception_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_pyprowl
) -> None:
    """Sending a message via Prowl with a general unhandled exception."""
    mock_pyprowl.notify.side_effect = SyntaxError

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

    assert mock_pyprowl.notify.call_count > 0
