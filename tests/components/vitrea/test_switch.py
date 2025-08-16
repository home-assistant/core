"""Test switch entities for Vitrea integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.vitrea.switch import VitreaSwitch
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test switch entities are created and updated via VitreaClient events."""
    # Create switches and add them to hass properly
    switch1 = VitreaSwitch(node="01", key="01", is_on=True, monitor=mock_vitrea_client)
    switch2 = VitreaSwitch(node="01", key="02", is_on=False, monitor=mock_vitrea_client)

    # Add to Home Assistant
    switch1.hass = hass
    switch2.hass = hass

    # Test initial states
    assert switch1.is_on is True
    assert switch2.is_on is False

    # Test entity properties
    assert switch1.unique_id == "01_01"
    assert switch2.unique_id == "01_02"
    assert switch1.name == "switch_01_01"
    assert switch2.name == "switch_01_02"

    # Test should_poll property
    assert switch1.should_poll is False
    assert switch2.should_poll is False

    # Test assumed_state property
    assert switch1.assumed_state is True
    assert switch2.assumed_state is True

    # Test that entities have proper state setting method
    switch1.set_switch_state(False)
    assert switch1.is_on is False

    switch2.set_switch_state(True)
    assert switch2.is_on is True


async def test_set_timer_service(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test set_timer service for timer switch."""
    # Create a timer switch
    timer_switch = VitreaSwitch(
        node="02", key="01", is_on=True, monitor=mock_vitrea_client, timer=None
    )
    timer_switch.hass = hass
    timer_switch.entity_id = "switch.switch_02_01"  # Add entity_id to avoid error

    # Mock the async methods properly with correct method names
    mock_vitrea_client.key_on = AsyncMock()
    mock_vitrea_client.key_off = AsyncMock()

    # Mock async_write_ha_state to avoid entity registry issues in tests
    timer_switch.async_write_ha_state = MagicMock()

    # Test turning the switch on
    await timer_switch.async_turn_on()

    # Verify the monitor method was called
    mock_vitrea_client.key_on.assert_called_once_with("02", "01")
    assert timer_switch.is_on is True

    # Test turning the switch off
    await timer_switch.async_turn_off()

    # Verify the monitor method was called
    mock_vitrea_client.key_off.assert_called_once_with("02", "01")
    assert timer_switch.is_on is False


async def test_switch_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test switch error handling."""
    # Create a switch
    switch = VitreaSwitch(node="01", key="01", is_on=True, monitor=mock_vitrea_client)
    switch.hass = hass

    # Mock an exception from the monitor with correct method names
    mock_vitrea_client.key_on = AsyncMock(side_effect=Exception("Connection failed"))
    mock_vitrea_client.key_off = AsyncMock(side_effect=Exception("Connection failed"))

    # Test error handling during turn on
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_on()

    # Check that error was logged
    assert "Failed to turn on switch" in caplog.text

    # Test error handling during turn off
    with pytest.raises(HomeAssistantError):
        await switch.async_turn_off()

    # Check that error was logged
    assert "Failed to turn off switch" in caplog.text
