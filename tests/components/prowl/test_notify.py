"""Test the Prowl notifications."""

from typing import Any
from unittest.mock import Mock

import prowlpy
import pytest

from homeassistant.components import notify
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import ENTITY_ID, TEST_API_KEY

from tests.common import MockConfigEntry

SERVICE_DATA = {"message": "Test Notification", "title": "Test Title"}

EXPECTED_SEND_PARAMETERS = {
    "application": "Home-Assistant",
    "event": "Test Title",
    "description": "Test Notification",
    "priority": 0,
    "url": None,
}


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_send_notification_service(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
) -> None:
    """Set up Prowl, call notify service, and check API call."""
    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    await hass.services.async_call(
        notify.DOMAIN,
        DOMAIN,
        SERVICE_DATA,
        blocking=True,
    )

    mock_prowlpy.send.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


async def test_send_notification_entity_service(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    mock_prowlpy_config_entry: MockConfigEntry,
) -> None:
    """Set up Prowl via config entry, call notify service, and check API call."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, notify.SERVICE_SEND_MESSAGE)
    await hass.services.async_call(
        notify.DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {
            "entity_id": ENTITY_ID,
            notify.ATTR_MESSAGE: SERVICE_DATA["message"],
            notify.ATTR_TITLE: SERVICE_DATA["title"],
        },
        blocking=True,
    )

    mock_prowlpy.send.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "raised_exception", "exception_message"),
    [
        (
            prowlpy.APIError("Internal server error"),
            HomeAssistantError,
            "Unexpected error when calling Prowl API",
        ),
        (
            TimeoutError,
            HomeAssistantError,
            "Timeout accessing Prowl API",
        ),
        (
            prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}"),
            HomeAssistantError,
            "Invalid API key for Prowl service",
        ),
        (
            prowlpy.APIError(
                "Not accepted: Your IP address has exceeded the API limit"
            ),
            HomeAssistantError,
            "Prowl service reported: exceeded rate limit",
        ),
        (
            SyntaxError(),
            SyntaxError,
            None,
        ),
    ],
)
async def test_fail_send_notification_entity_service(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    mock_prowlpy_config_entry: MockConfigEntry,
    prowlpy_side_effect: Exception,
    raised_exception: type[Exception],
    exception_message: str | None,
) -> None:
    """Set up Prowl via config entry, call notify service, and check API call."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_prowlpy.send.side_effect = prowlpy_side_effect

    assert hass.services.has_service(notify.DOMAIN, notify.SERVICE_SEND_MESSAGE)
    with pytest.raises(raised_exception, match=exception_message):
        await hass.services.async_call(
            notify.DOMAIN,
            notify.SERVICE_SEND_MESSAGE,
            {
                "entity_id": ENTITY_ID,
                notify.ATTR_MESSAGE: SERVICE_DATA["message"],
                notify.ATTR_TITLE: SERVICE_DATA["title"],
            },
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "raised_exception", "exception_message"),
    [
        (
            prowlpy.APIError("Internal server error"),
            HomeAssistantError,
            "Unexpected error when calling Prowl API",
        ),
        (
            TimeoutError,
            HomeAssistantError,
            "Timeout accessing Prowl API",
        ),
        (
            prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}"),
            HomeAssistantError,
            "Invalid API key for Prowl service",
        ),
        (
            prowlpy.APIError(
                "Not accepted: Your IP address has exceeded the API limit"
            ),
            HomeAssistantError,
            "Prowl service reported: exceeded rate limit",
        ),
        (
            SyntaxError(),
            SyntaxError,
            None,
        ),
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_fail_send_notification(
    hass: HomeAssistant,
    mock_prowlpy: Mock,
    prowlpy_side_effect: Exception,
    raised_exception: type[Exception],
    exception_message: str | None,
) -> None:
    """Sending a message via Prowl with a failure."""
    mock_prowlpy.send.side_effect = prowlpy_side_effect

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    with pytest.raises(raised_exception, match=exception_message):
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            SERVICE_DATA,
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


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

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    with pytest.raises(SyntaxError):
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            SERVICE_DATA,
            blocking=True,
        )

    mock_prowlpy.send.assert_called_once_with(**expected_send_parameters)
