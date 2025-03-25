"""Test the Prowl notifications."""

import pytest

from homeassistant.components.prowl.notify import ProwlNotificationService
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_send_notification(hass: HomeAssistant, mock_pyprowl_success) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    await prowl.async_send_message(
        "Test Notification", data={"url": "http://localhost"}
    )

    assert mock_pyprowl_success.notify.call_count > 0


@pytest.mark.asyncio
async def test_fail_send_notification(hass: HomeAssistant, mock_pyprowl_fail) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(HomeAssistantError):
        await prowl.async_send_message(
            "Test Notification", data={"url": "http://localhost"}
        )

    assert mock_pyprowl_fail.notify.call_count > 0


@pytest.mark.asyncio
async def test_timeout_send_notification(
    hass: HomeAssistant, mock_pyprowl_timeout
) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(TimeoutError):
        await prowl.async_send_message(
            "Test Notification", data={"url": "http://localhost"}
        )

    assert mock_pyprowl_timeout.notify.call_count > 0


@pytest.mark.asyncio
async def test_bad_api_key_send_notification(
    hass: HomeAssistant, mock_pyprowl_forbidden
) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(ConfigEntryAuthFailed):
        await prowl.async_send_message(
            "Test Notification", data={"url": "http://localhost"}
        )

    assert mock_pyprowl_forbidden.notify.call_count > 0


@pytest.mark.asyncio
async def test_unknown_exception_send_notification(
    hass: HomeAssistant, mock_pyprowl_syntax_error
) -> None:
    """Test sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(SyntaxError):
        await prowl.async_send_message(
            "Test Notification", data={"url": "http://localhost"}
        )

    assert mock_pyprowl_syntax_error.notify.call_count > 0


@pytest.mark.asyncio
async def test_verify_api_key_not_valid(
    hass: HomeAssistant, mock_pyprowl_forbidden
) -> None:
    """Test API error during API key verification."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    assert not await prowl.async_verify_key()
    assert mock_pyprowl_forbidden.verify_key.call_count > 0


@pytest.mark.asyncio
async def test_verify_api_key_failure(hass: HomeAssistant, mock_pyprowl_fail) -> None:
    """Test API error during API key verification."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(HomeAssistantError):
        await prowl.async_verify_key()
    assert mock_pyprowl_fail.verify_key.call_count > 0


@pytest.mark.asyncio
async def test_verify_api_key_syntax_error(
    hass: HomeAssistant, mock_pyprowl_syntax_error
) -> None:
    """Test Syntax error in pyprowl during API key verification."""
    prowl = ProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(SyntaxError):
        await prowl.async_verify_key()
    assert mock_pyprowl_syntax_error.verify_key.call_count > 0
