"""Test the Prowl notifications."""

import pytest

from homeassistant.components.prowl.notify import ProwlNotificationService
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_API_KEY, TEST_NAME


@pytest.mark.asyncio
async def test_send_notification(hass: HomeAssistant, mock_pyprowl_success) -> None:
    """Sending a notification message via Prowl."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    await prowl.async_send_message("Test Notification", "Test Title")

    assert mock_pyprowl_success.notify.call_count > 0


@pytest.mark.asyncio
async def test_fail_send_notification(hass: HomeAssistant, mock_pyprowl_fail) -> None:
    """Sending a message via Prowl with a failure."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(HomeAssistantError):
        await prowl.async_send_message("Test Notification", "Test Title")

    assert mock_pyprowl_fail.notify.call_count > 0


@pytest.mark.asyncio
async def test_timeout_send_notification(
    hass: HomeAssistant, mock_pyprowl_timeout
) -> None:
    """Sending a message via Prowl with a timeout."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(TimeoutError):
        await prowl.async_send_message("Test Notification", "Test Title")

    assert mock_pyprowl_timeout.notify.call_count > 0


@pytest.mark.asyncio
async def test_bad_api_key_send_notification(
    hass: HomeAssistant, mock_pyprowl_forbidden
) -> None:
    """Sending a message via Prowl with a bad API key."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(ConfigEntryAuthFailed):
        await prowl.async_send_message("Test Notification", "Test Title")

    assert mock_pyprowl_forbidden.notify.call_count > 0


@pytest.mark.asyncio
async def test_unknown_exception_send_notification(
    hass: HomeAssistant, mock_pyprowl_syntax_error
) -> None:
    """Sending a message via Prowl with an unhandled exception from the library."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(SyntaxError):
        await prowl.async_send_message("Test Notification", "Test Title")

    assert mock_pyprowl_syntax_error.notify.call_count > 0


@pytest.mark.asyncio
async def test_verify_api_key_not_valid(
    hass: HomeAssistant, mock_pyprowl_forbidden
) -> None:
    """API key verification in Prowl with an invalid key."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    assert not await prowl.async_verify_key()
    assert mock_pyprowl_forbidden.verify_key.call_count > 0


@pytest.mark.asyncio
async def test_verify_api_key_failure(hass: HomeAssistant, mock_pyprowl_fail) -> None:
    """API key verification in Prowl with a failure."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(HomeAssistantError):
        await prowl.async_verify_key()
    assert mock_pyprowl_fail.verify_key.call_count > 0


@pytest.mark.asyncio
async def test_verify_api_key_syntax_error(
    hass: HomeAssistant, mock_pyprowl_syntax_error
) -> None:
    """API key verification in Prowl with an unhandled exception from the library."""
    prowl = ProwlNotificationService(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(SyntaxError):
        await prowl.async_verify_key()
    assert mock_pyprowl_syntax_error.verify_key.call_count > 0
