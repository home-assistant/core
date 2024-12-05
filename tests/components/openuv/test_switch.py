"""Test Openuv switch."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.openuv.sunscreen_reminder import SunscreenReminder
from homeassistant.components.openuv.switch import SunscreenReminderSwitch
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant


@pytest.fixture
def hass_instance():
    """Fixture to create a HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def sunscreen_reminder(hass_instance):
    """Fixture to create a mock SunscreenReminder instance."""
    reminder = MagicMock(spec=SunscreenReminder)
    reminder.async_initialize = AsyncMock()
    reminder.async_cleanup = AsyncMock()
    reminder.hass = hass_instance  # Mock hass on the reminder instance
    return reminder


@pytest.fixture
def switch_entity(hass_instance, sunscreen_reminder):
    """Fixture to create a SunscreenReminderSwitch instance."""
    switch = SunscreenReminderSwitch(sunscreen_reminder)
    switch.hass = hass_instance  # Set hass on the switch entity
    switch.async_write_ha_state = AsyncMock()  # Mock the state writing method
    return switch


async def test_switch_initial_state(switch_entity: SwitchEntity) -> None:
    """Test the initial state of the switch."""
    assert not switch_entity.is_on
    assert switch_entity.name == "Sunscreen Reminder"
    assert switch_entity.unique_id == "sunscreen_reminder_switch"
    assert switch_entity.icon == "mdi:emoticon-cool-outline"


async def test_turn_on_switch(
    switch_entity: SwitchEntity, sunscreen_reminder: SunscreenReminder
) -> None:
    """Test turning the switch on."""
    assert not switch_entity.is_on  # Initial state is off

    # Turn the switch on
    await switch_entity.async_turn_on()
    assert switch_entity.is_on  # State should now be on

    # Verify that async_initialize was called
    sunscreen_reminder.async_initialize.assert_called_once()

    # Verify state is written to Home Assistant
    switch_entity.async_write_ha_state.assert_called_once()


async def test_turn_off_switch(
    switch_entity: SwitchEntity, sunscreen_reminder: SunscreenReminder
) -> None:
    """Test turning the switch off."""
    # First, turn the switch on
    await switch_entity.async_turn_on()
    assert switch_entity.is_on  # Verify it's on

    # Turn the switch off
    await switch_entity.async_turn_off()
    assert not switch_entity.is_on  # State should now be off

    # Verify that async_cleanup was called
    sunscreen_reminder.async_cleanup.assert_called_once()

    # Verify state is written to Home Assistant
    switch_entity.async_write_ha_state.assert_called()
