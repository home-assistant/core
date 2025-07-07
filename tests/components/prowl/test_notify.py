"""Test the Prowl notifications."""

import pytest

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.prowl.notify import ProwlNotificationEntity
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_API_KEY, TEST_NAME


async def test_send_notification_service(
    hass: HomeAssistant, mock_pyprowl_config_entry, mock_pyprowl_success
) -> None:
    """Set up Prowl config entry, call notify service, and check API call."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            "entity_id": NOTIFY_DOMAIN + "." + TEST_NAME,
            "message": "Test Notification",
            "title": "Test Title",
        },
        blocking=True,
    )

    assert mock_pyprowl_success.notify.call_count > 0


async def test_fail_send_notification(
    hass: HomeAssistant, mock_pyprowl_config_entry, mock_pyprowl
) -> None:
    """Sending a message via Prowl with a failure, without patching verify method."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_pyprowl.notify.side_effect = Exception("500 Error")

    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                "entity_id": NOTIFY_DOMAIN + "." + TEST_NAME,
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_pyprowl.notify.call_count > 0


async def test_timeout_send_notification(
    hass: HomeAssistant, mock_pyprowl_config_entry, mock_pyprowl
) -> None:
    """Sending a message via Prowl with a timeout."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_pyprowl.notify.side_effect = TimeoutError

    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    with pytest.raises(TimeoutError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                "entity_id": NOTIFY_DOMAIN + "." + TEST_NAME,
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_pyprowl.notify.call_count > 0


async def test_bad_api_key_send_notification(
    hass: HomeAssistant, mock_pyprowl_config_entry, mock_pyprowl
) -> None:
    """Sending a message via Prowl with a bad API key."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_pyprowl.notify.side_effect = Exception("401 Unauthorized")

    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    with pytest.raises(ConfigEntryAuthFailed):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                "entity_id": NOTIFY_DOMAIN + "." + TEST_NAME,
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_pyprowl.notify.call_count > 0


async def test_unknown_exception_send_notification(
    hass: HomeAssistant, mock_pyprowl_config_entry, mock_pyprowl
) -> None:
    """Sending a message via Prowl with an unhandled exception from the library."""
    mock_pyprowl_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_pyprowl_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_pyprowl.notify.side_effect = SyntaxError

    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    with pytest.raises(SyntaxError):
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                "entity_id": NOTIFY_DOMAIN + "." + TEST_NAME,
                "message": "Test Notification",
                "title": "Test Title",
            },
            blocking=True,
        )

    assert mock_pyprowl.notify.call_count > 0


async def test_verify_api_key_not_valid(
    hass: HomeAssistant, mock_pyprowl_forbidden
) -> None:
    """API key verification in Prowl with an invalid key."""
    prowl = ProwlNotificationEntity(hass, TEST_NAME, TEST_API_KEY)

    assert not await prowl.async_verify_key()
    assert mock_pyprowl_forbidden.verify_key.call_count > 0


async def test_verify_api_key_failure(hass: HomeAssistant, mock_pyprowl_fail) -> None:
    """API key verification in Prowl with a failure."""

    prowl = ProwlNotificationEntity(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(HomeAssistantError):
        assert not await prowl.async_verify_key()
    assert mock_pyprowl_fail.verify_key.call_count > 0


async def test_verify_api_key_syntax_error(
    hass: HomeAssistant, mock_pyprowl_syntax_error
) -> None:
    """API key verification in Prowl with an unhandled exception from the library."""
    prowl = ProwlNotificationEntity(hass, TEST_NAME, TEST_API_KEY)

    with pytest.raises(SyntaxError):
        assert not await prowl.async_verify_key()
    assert mock_pyprowl_syntax_error.verify_key.call_count > 0
