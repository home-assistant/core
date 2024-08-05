"""Tests for tibber notification service."""

from asyncio import TimeoutError
from unittest.mock import MagicMock

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_notification_services(
    recorder_mock: Recorder, hass: HomeAssistant, mock_tibber_setup: MagicMock
) -> None:
    """Test create entry from user input."""
    # Assert notify entity has been added
    notify_state = hass.states.get("notify.tibber")
    assert notify_state is not None

    # Assert legacy notify service hass been added
    assert hass.services.has_service("notify", DOMAIN)

    # Test legacy notify service
    service = "tibber"
    service_data = {"message": "The message", "title": "A title"}
    await hass.services.async_call("notify", service, service_data, blocking=True)
    calls: MagicMock = mock_tibber_setup.send_notification

    calls.assert_called_once_with(message="The message", title="A title")
    calls.reset_mock()

    # Test notify entity service
    service = "send_message"
    service_data = {
        "entity_id": "notify.tibber",
        "message": "The message",
        "title": "A title",
    }
    await hass.services.async_call("notify", service, service_data, blocking=True)
    calls.assert_called_once_with("A title", "The message")
    calls.reset_mock()

    calls.side_effect = TimeoutError

    with pytest.raises(HomeAssistantError):
        # Test legacy notify service
        await hass.services.async_call(
            "notify",
            service="tibber",
            service_data={"message": "The message", "title": "A title"},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        # Test notify entity service
        await hass.services.async_call(
            "notify",
            service="send_message",
            service_data={
                "entity_id": "notify.tibber",
                "message": "The message",
                "title": "A title",
            },
            blocking=True,
        )
