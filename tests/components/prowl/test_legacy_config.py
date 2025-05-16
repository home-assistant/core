"""Test the legacy services.yaml configuration."""

import pytest

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.prowl import DOMAIN
from homeassistant.components.prowl.notify import LegacyProwlNotificationService
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_legacy_platform_send_message(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_pyprowl_success
) -> None:
    """Sending a notification message to Prowl via the legacy notify platform."""
    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    await hass.services.async_call(NOTIFY_DOMAIN, DOMAIN, {"message": "test"}, False)
    assert mock_pyprowl_success.notify.call_count > 0


@pytest.mark.asyncio
async def test_legacy_send_message(hass: HomeAssistant, mock_pyprowl_success) -> None:
    """Sending a notification message via the Legacy Prowl object."""
    prowl = LegacyProwlNotificationService(hass, TEST_API_KEY)
    await prowl.async_send_message("Test Notification", data={"url": "http://test.url"})

    assert mock_pyprowl_success.notify.call_count > 0


@pytest.mark.asyncio
async def test_fail_legacy_send_notification(
    hass: HomeAssistant, configure_prowl_through_yaml, mock_pyprowl_fail
) -> None:
    """Sending a message via Legacy Prowl with a failure."""
    prowl = LegacyProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(HomeAssistantError):
        await prowl.async_send_message("Test Notification")

    assert mock_pyprowl_fail.notify.call_count > 0


@pytest.mark.asyncio
async def test_timeout_legacy_send_notification(
    hass: HomeAssistant, mock_pyprowl_timeout
) -> None:
    """Sending a message via Legacy Prowl with a timeout."""
    prowl = LegacyProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(TimeoutError):
        await prowl.async_send_message("Test Notification")

    assert mock_pyprowl_timeout.notify.call_count > 0


@pytest.mark.asyncio
async def test_bad_api_key_legacy_send_notification(
    hass: HomeAssistant, mock_pyprowl_forbidden
) -> None:
    """Sending a message via Legacy Prowl with a bad API key."""
    prowl = LegacyProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(ConfigEntryAuthFailed):
        await prowl.async_send_message("Test Notification")

    assert mock_pyprowl_forbidden.notify.call_count > 0


@pytest.mark.asyncio
async def test_unknown_exception_legacy_send_notification(
    hass: HomeAssistant, mock_pyprowl_syntax_error
) -> None:
    """Sending a message via Legacy Prowl getting an unhandled exception from the library."""
    prowl = LegacyProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(SyntaxError):
        await prowl.async_send_message("Test Notification")

    assert mock_pyprowl_syntax_error.notify.call_count > 0


@pytest.mark.asyncio
async def test_legacy_verify_api_key_syntax_error(
    hass: HomeAssistant, mock_pyprowl_syntax_error
) -> None:
    """API key verification in Prowl with an unhandled exception from the library."""
    prowl = LegacyProwlNotificationService(hass, TEST_API_KEY)

    with pytest.raises(SyntaxError):
        await prowl.async_verify_key()
    assert mock_pyprowl_syntax_error.verify_key.call_count > 0
