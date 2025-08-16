"""Test number entities for Vitrea integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from vitreaclient.constants import DeviceStatus

from homeassistant.components.vitrea import VitreaRuntimeData
from homeassistant.components.vitrea.number import (
    VitreaTimerControl,
    _handle_timer_event,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test number entities are created for timer switches via VitreaClient events."""
    # Create timer controls and add them to hass properly
    timer1 = VitreaTimerControl(
        node="02", key="01", initial_value="120", monitor=mock_vitrea_client
    )

    # Mock the hass attribute and entity_id to make them behave like real entities
    timer1.hass = hass
    timer1.entity_id = "number.timer_02_01"
    # Don't override _attr_unique_id - use the one from constructor (02_01)

    timers = [timer1]

    # Update the config entry's runtime_data with proper VitreaRuntimeData dataclass
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=[], switches=[], timers=timers
    )

    # The integration is already set up by init_integration fixture
    await hass.async_block_till_done()

    # Test basic properties
    assert timer1.native_value == 120
    assert timer1.unique_id == "02_01"  # Fixed: use actual unique_id from constructor
    assert timer1.name == "timer_02_01"
    assert timer1.device_class == "duration"
    assert timer1.native_unit_of_measurement == "min"
    assert timer1.native_min_value == 0
    assert timer1.native_max_value == 120

    # Test event handling - create a mock event that matches an existing timer
    event = MagicMock(status=DeviceStatus.BOILER_ON, node="02", key="01", data="150")

    # Mock the async_write_ha_state method to avoid the hass reference issue
    timer1.async_write_ha_state = MagicMock()

    _handle_timer_event(init_integration, event)
    await hass.async_block_till_done()

    # Verify the event handler found the correct timer and updated its state
    timer1.async_write_ha_state.assert_called_once()

    # Verify timer value was updated
    assert timer1._attr_native_value == 150


async def test_set_value_service(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test set_value service for timer number entity."""
    # Create a timer control entity
    timer = VitreaTimerControl(
        node="02", key="01", initial_value="120", monitor=mock_vitrea_client
    )
    timer.hass = hass
    timer.entity_id = "number.timer_02_01"
    timer._attr_unique_id = "timer_02_01"

    # Mock the set_timer method as async
    mock_vitrea_client.set_timer = AsyncMock()

    # Test the set value method directly
    await timer.async_set_native_value(180)

    # Verify set_timer was called with correct parameters
    mock_vitrea_client.set_timer.assert_called_with("02", "01", 180)
    assert timer.native_value == 180


async def test_number_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test number error handling."""
    # Create a timer control entity
    timer = VitreaTimerControl(
        node="02", key="01", initial_value="120", monitor=mock_vitrea_client
    )
    timer.hass = hass
    timer.entity_id = "number.timer_02_01"
    timer._attr_unique_id = "timer_02_01"

    # Make set_timer fail
    mock_vitrea_client.set_timer = AsyncMock(side_effect=OSError("Communication error"))

    # Try to set value
    await timer.async_set_native_value(200)

    # Check error was logged
    assert "Failed to set timer value" in caplog.text
    assert "Communication error" in caplog.text
