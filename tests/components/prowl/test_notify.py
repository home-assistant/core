"""Test the Prowl notifications."""

from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import probatio
import prowlpy
import pytest

from homeassistant.components import notify
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

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
    mock_prowlpy: AsyncMock,
) -> None:
    """Set up Prowl, call notify service, and check API call."""
    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    await hass.services.async_call(
        notify.DOMAIN,
        DOMAIN,
        SERVICE_DATA,
        blocking=True,
    )

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


async def test_send_notification_entity_service(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
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

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "raised_exception", "exception_message"),
    [
        (
            prowlpy.APIError("Internal server error"),
            HomeAssistantError,
            "Unexpected error when calling the Prowl API: Internal server error",
        ),
        (
            TimeoutError,
            HomeAssistantError,
            "Timeout accessing the Prowl API",
        ),
        (
            prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}"),
            HomeAssistantError,
            "Invalid API key for the Prowl service",
        ),
        (
            prowlpy.APIError(
                "Not accepted: Your IP address has exceeded the API limit"
            ),
            HomeAssistantError,
            "The Prowl service reported that the rate limit was exceeded",
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
    mock_prowlpy: AsyncMock,
    mock_prowlpy_config_entry: MockConfigEntry,
    prowlpy_side_effect: Exception,
    raised_exception: type[Exception],
    exception_message: str | None,
) -> None:
    """Set up Prowl via config entry, call notify service, and check API call."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_prowlpy.post.side_effect = prowlpy_side_effect

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

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "raised_exception", "exception_message"),
    [
        (
            prowlpy.APIError("Internal server error"),
            HomeAssistantError,
            "Unexpected error when calling the Prowl API: Internal server error",
        ),
        (
            TimeoutError,
            HomeAssistantError,
            "Timeout accessing the Prowl API",
        ),
        (
            prowlpy.APIError(f"Invalid API key: {TEST_API_KEY}"),
            HomeAssistantError,
            "Invalid API key for the Prowl service",
        ),
        (
            prowlpy.APIError(
                "Not accepted: Your IP address has exceeded the API limit"
            ),
            HomeAssistantError,
            "The Prowl service reported that the rate limit was exceeded",
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
    mock_prowlpy: AsyncMock,
    prowlpy_side_effect: Exception,
    raised_exception: type[Exception],
    exception_message: str | None,
) -> None:
    """Sending a message via Prowl with a failure."""
    mock_prowlpy.post.side_effect = prowlpy_side_effect

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    with pytest.raises(raised_exception, match=exception_message):
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            SERVICE_DATA,
            blocking=True,
        )

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


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
    mock_prowlpy: AsyncMock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Sending a message via Prowl with a general unhandled exception."""
    mock_prowlpy.post.side_effect = SyntaxError

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)
    with pytest.raises(SyntaxError):
        await hass.services.async_call(
            notify.DOMAIN,
            DOMAIN,
            SERVICE_DATA,
            blocking=True,
        )

    mock_prowlpy.post.assert_called_once_with(**expected_send_parameters)


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        pytest.param(
            {notify.ATTR_MESSAGE: "Test Notification"},
            {
                "application": "Home-Assistant",
                "event": notify.ATTR_TITLE_DEFAULT,
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
            id="message_only",
        ),
        pytest.param(
            {
                notify.ATTR_MESSAGE: "Test Notification",
                notify.ATTR_TITLE: "Test Title",
                "priority": "emergency",
                "url": "https://www.home-assistant.io",
            },
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 2,
                "url": "https://www.home-assistant.io",
            },
            id="all_options",
        ),
        pytest.param(
            {notify.ATTR_MESSAGE: "Test Notification", "priority": "very_low"},
            {
                "application": "Home-Assistant",
                "event": notify.ATTR_TITLE_DEFAULT,
                "description": "Test Notification",
                "priority": -2,
                "url": None,
            },
            id="very_low_priority",
        ),
    ],
)
@pytest.mark.usefixtures("prowl_notification_entity")
async def test_prowl_send_message_action(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    freezer: FrozenDateTimeFactory,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Test the prowl.send_message entity action."""
    freezer.move_to("2026-10-03T12:00:00+00:00")
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {"entity_id": ENTITY_ID, **service_data},
        blocking=True,
    )

    mock_prowlpy.post.assert_called_once_with(**expected_send_parameters)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == "2026-10-03T12:00:00+00:00"


@pytest.mark.parametrize(
    "service_data",
    [
        pytest.param({"priority": "invalid"}, id="invalid_priority"),
        pytest.param({"url": "not a url"}, id="invalid_url"),
    ],
)
@pytest.mark.usefixtures("prowl_notification_entity")
async def test_prowl_send_message_action_invalid(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    service_data: dict[str, Any],
) -> None:
    """Test the prowl.send_message entity action rejects invalid input."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            notify.SERVICE_SEND_MESSAGE,
            {
                "entity_id": ENTITY_ID,
                notify.ATTR_MESSAGE: "Test Notification",
                **service_data,
            },
            blocking=True,
        )

    mock_prowlpy.post.assert_not_called()


@pytest.mark.usefixtures("prowl_notification_entity")
async def test_prowl_send_message_action_error(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
) -> None:
    """Test the prowl.send_message entity action raises on API errors."""
    mock_prowlpy.post.side_effect = TimeoutError

    with pytest.raises(HomeAssistantError, match="Timeout accessing the Prowl API"):
        await hass.services.async_call(
            DOMAIN,
            notify.SERVICE_SEND_MESSAGE,
            {"entity_id": ENTITY_ID, notify.ATTR_MESSAGE: "Test Notification"},
            blocking=True,
        )

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("configure_prowl_through_yaml", "mock_prowlpy")
async def test_deprecated_legacy_notify_action(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy notify action creates a deprecation issue."""
    assert not issue_registry.async_get_issue(
        DOMAIN, f"deprecated_notify_action_{DOMAIN}"
    )

    await hass.services.async_call(
        notify.DOMAIN,
        DOMAIN,
        SERVICE_DATA,
        blocking=True,
    )

    issue = issue_registry.async_get_issue(DOMAIN, f"deprecated_notify_action_{DOMAIN}")
    assert issue
    assert issue.breaks_in_ha_version == "2027.5.0"
    assert issue.translation_placeholders["action"] == f"notify.{DOMAIN}"
