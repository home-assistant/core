"""Test Openuv sunscreen reminder."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from homeassistant.components.openuv.sunscreen_reminder import SunscreenReminder
from homeassistant.core import HomeAssistant

LOCAL_TIMEZONE = "Europe/Stockholm"


@pytest.fixture
def sunscreen_reminder(hass: HomeAssistant):
    """Fixture to initialize SunscreenReminder."""
    return SunscreenReminder(hass)


async def test_initialize_sunscreen_reminder(sunscreen_reminder) -> None:
    """Test SunscreenReminder initialization."""
    # Initialize once
    await sunscreen_reminder.async_initialize()
    assert sunscreen_reminder.periodic_task is not None

    # Attempt to initialize again (should skip reinitialization)
    await sunscreen_reminder.async_initialize()
    assert sunscreen_reminder.periodic_task is not None  # Task remains unchanged


async def test_notification_sent_when_uv_is_high(
    hass: HomeAssistant, sunscreen_reminder
) -> None:
    """Test that a notification is sent when UV index is above the threshold."""
    # Mock the persistent_notification.create service
    mock_create = AsyncMock()
    hass.services.async_register(
        "persistent_notification",
        "create",
        mock_create,
    )

    # Set states for the switch and UV index
    hass.states.async_set("switch.sunscreen_reminder", "on")  # Switch is ON
    hass.states.async_set("sensor.openuv_current_uv_index", "6.0")  # Above threshold
    await hass.async_block_till_done()

    # Trigger the periodic check
    await sunscreen_reminder._periodic_check(datetime.now())

    # Ensure the service was called exactly once
    mock_create.assert_called_once()

    # Extract the call arguments
    call = mock_create.call_args[0][0]  # The ServiceCall object

    # Validate the service domain and method
    assert call.domain == "persistent_notification"
    assert call.service == "create"

    # Validate the parameters passed to the service
    now = datetime.now(ZoneInfo(LOCAL_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S %Z")
    assert call.data == {
        "message": f"Save your skin, apply sunscreen!\n\n{now}",
        "title": "Sunscreen Reminder",
    }


async def test_no_notification_when_uv_is_low(
    hass: HomeAssistant, sunscreen_reminder
) -> None:
    """Test that no notification is sent when UV index is below the threshold."""
    # Mock the persistent_notification.create service
    mock_create = AsyncMock()
    hass.services.async_register(
        "persistent_notification",
        "create",
        mock_create,
    )

    # Set states for the switch and UV index
    hass.states.async_set("switch.sunscreen_reminder", "on")  # Switch is ON
    hass.states.async_set("sensor.openuv_current_uv_index", "2.0")  # Below threshold
    await hass.async_block_till_done()

    # Trigger the periodic check
    await sunscreen_reminder._periodic_check(datetime.now())

    # Ensure the service was not called
    mock_create.assert_not_called()


async def test_no_notification_when_switch_is_off(
    hass: HomeAssistant, sunscreen_reminder
) -> None:
    """Test no notification is sent when the switch is off."""
    # Mock the persistent_notification.create service
    mock_create = AsyncMock()
    hass.services.async_register(
        "persistent_notification",
        "create",
        mock_create,
    )

    # Set states for the switch and UV index
    hass.states.async_set("switch.sunscreen_reminder", "off")  # Switch is off
    hass.states.async_set("sensor.openuv_current_uv_index", "5.0")  # Above threshold
    await hass.async_block_till_done()

    # Trigger the periodic check
    await sunscreen_reminder._periodic_check(datetime.now())

    # Assert no notification was created
    mock_create.assert_not_called()


async def test_cleanup_sunscreen_reminder(sunscreen_reminder) -> None:
    """Test SunscreenReminder cleanup."""
    # Mock the periodic task
    mock_task = MagicMock()
    sunscreen_reminder.periodic_task = mock_task

    # Perform cleanup
    await sunscreen_reminder.async_cleanup()

    # Assert that the periodic task was canceled
    mock_task.assert_called_once()
    assert sunscreen_reminder.periodic_task is None
