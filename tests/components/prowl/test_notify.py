"""Test the Prowl notifications."""

from typing import Any
from unittest.mock import Mock

import prowlpy
import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_API_KEY


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        (
            {"message": "Test Notification", "title": "Test Title"},
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
        )
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_send_notification_service(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Set up Prowl, call notify service, and check API call."""
    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        service_data,
        blocking=True,
    )

    mock_prowlpy.send.assert_called_once_with(**expected_send_parameters)


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        (
            {"message": "Test Notification", "title": "Test Title"},
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
        )
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_fail_send_notification(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Sending a message via Prowl with a failure."""
    mock_prowlpy.send.side_effect = prowlpy.APIError("Internal server error")

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            service_data,
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**expected_send_parameters)


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        (
            {"message": "Test Notification", "title": "Test Title"},
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
        )
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_send_notification_timeout(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Sending a message via Prowl with a timeout."""
    mock_prowlpy.send.side_effect = TimeoutError

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(HomeAssistantError, match="Timeout accessing Prowl API"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            service_data,
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**expected_send_parameters)


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        (
            {"message": "Test Notification", "title": "Test Title"},
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
        )
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_forbidden_send_notification(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Sending a message via Prowl with a forbidden error."""
    mock_prowlpy.send.side_effect = prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}")

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(HomeAssistantError, match="Invalid API key for Prowl service"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            service_data,
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**expected_send_parameters)


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        (
            {"message": "Test Notification", "title": "Test Title"},
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
        )
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_rate_limited_send_notification(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Sending a message via Prowl with a forbidden error."""
    mock_prowlpy.send.side_effect = prowlpy.APIError(
        "Not accepted: Your IP address has exceeded the API limit"
    )

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(HomeAssistantError, match="Prowl service reported: exceeded rate limit"):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            service_data,
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**expected_send_parameters)


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        (
            {"message": "Test Notification", "title": "Test Title"},
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
        )
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_other_exception_send_notification(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Sending a message via Prowl with a general unhandled exception."""
    mock_prowlpy.send.side_effect = SyntaxError

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    with pytest.raises(SyntaxError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DOMAIN,
            service_data,
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**expected_send_parameters)
