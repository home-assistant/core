"""Test the vitrea cover platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from vitreaclient.constants import DeviceStatus

from homeassistant.components.vitrea import VitreaRuntimeData
from homeassistant.components.vitrea.cover import VitreaCover, _handle_cover_event
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_cover_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test cover entities are created and updated via VitreaClient events."""
    # Create mock covers that are properly integrated with Home Assistant

    # Create covers and add them to hass properly
    cover1 = VitreaCover(
        node="03", key="01", position="050", monitor=mock_vitrea_client
    )
    cover2 = VitreaCover(
        node="03", key="02", position="100", monitor=mock_vitrea_client
    )
    cover3 = VitreaCover(
        node="03", key="03", position="000", monitor=mock_vitrea_client
    )

    # Mock the hass attribute and entity_id to make them behave like real entities
    cover1.hass = hass
    cover1.entity_id = "cover.cover_03_01"
    cover1._attr_unique_id = "03_01"

    cover2.hass = hass
    cover2.entity_id = "cover.cover_03_02"
    cover2._attr_unique_id = "03_02"

    cover3.hass = hass
    cover3.entity_id = "cover.cover_03_03"
    cover3._attr_unique_id = "03_03"

    covers = [cover1, cover2, cover3]

    # Update the config entry's runtime_data with modern VitreaRuntimeData structure
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=covers, switches=[], timers=[]
    )

    # The integration is already set up by init_integration fixture
    await hass.async_block_till_done()

    # Test event handling - create a mock event that matches an existing cover
    event = MagicMock(status=DeviceStatus.BLIND, node="03", key="01", data="075")

    # Mock the async_write_ha_state method to avoid the hass reference issue
    cover1.async_write_ha_state = MagicMock()
    cover2.async_write_ha_state = MagicMock()
    cover3.async_write_ha_state = MagicMock()

    _handle_cover_event(init_integration, event)
    await hass.async_block_till_done()

    # Verify the event handler found the correct cover and updated its state
    cover1.async_write_ha_state.assert_called_once()

    # Since entities are created programmatically, we'll verify through state updates
    assert len(covers) == 3
    # Verify cover position was updated - the event handler uses event.data, not event.position
    assert (
        cover1._attr_current_cover_position == 75
    )  # Position should be updated based on event


async def test_cover_open(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test opening a cover."""

    # Create a cover
    cover = VitreaCover(node="03", key="01", position="000", monitor=mock_vitrea_client)
    cover.hass = hass
    cover.entity_id = "cover.cover_03_01"
    cover._attr_unique_id = "03_01"

    # Add to runtime_data with proper dataclass
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=[cover], switches=[], timers=[]
    )
    await hass.async_block_till_done()

    # Mock the blind_open method
    mock_vitrea_client.blind_open = AsyncMock()

    # Test the cover open method directly
    await cover.async_open_cover()

    # Verify blind_open was called with correct parameters
    mock_vitrea_client.blind_open.assert_called_with("03", "01")


async def test_cover_close(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test closing a cover."""

    # Create a cover
    cover = VitreaCover(node="03", key="01", position="100", monitor=mock_vitrea_client)
    cover.hass = hass
    cover.entity_id = "cover.cover_03_01"
    cover._attr_unique_id = "03_01"

    # Add to runtime_data with proper dataclass
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=[cover], switches=[], timers=[]
    )
    await hass.async_block_till_done()

    # Mock the blind_close method
    mock_vitrea_client.blind_close = AsyncMock()

    # Test the cover close method directly
    await cover.async_close_cover()

    # Verify blind_close was called with correct parameters
    mock_vitrea_client.blind_close.assert_called_with("03", "01")


async def test_cover_set_position(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test setting cover position."""

    # Create a cover
    cover = VitreaCover(node="03", key="01", position="050", monitor=mock_vitrea_client)
    cover.hass = hass
    cover.entity_id = "cover.cover_03_01"
    cover._attr_unique_id = "03_01"

    # Add to runtime_data with proper dataclass
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=[cover], switches=[], timers=[]
    )
    await hass.async_block_till_done()

    # Mock the blind_percent method
    mock_vitrea_client.blind_percent = AsyncMock()

    # Test the cover set position method directly
    await cover.async_set_cover_position(position=75)

    # Verify blind_percent was called with correct parameters
    mock_vitrea_client.blind_percent.assert_called_with("03", "01", 75)


async def test_cover_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test stopping a cover."""

    # Create a cover
    cover = VitreaCover(node="03", key="01", position="050", monitor=mock_vitrea_client)
    cover.hass = hass
    cover.entity_id = "cover.cover_03_01"
    cover._attr_unique_id = "03_01"

    # Add to runtime_data with proper dataclass
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=[cover], switches=[], timers=[]
    )
    await hass.async_block_till_done()

    # Mock the blind_stop method
    mock_vitrea_client.blind_stop = AsyncMock()

    # Test the cover stop method directly
    await cover.async_stop_cover()

    # Verify blind_stop was called with correct parameters
    mock_vitrea_client.blind_stop.assert_called_with("03", "01")


async def test_cover_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test cover error handling."""

    # Create a cover
    cover = VitreaCover(node="03", key="01", position="050", monitor=mock_vitrea_client)
    cover.hass = hass
    cover.entity_id = "cover.cover_03_01"
    cover._attr_unique_id = "03_01"

    # Add to runtime_data with proper dataclass
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=[cover], switches=[], timers=[]
    )
    await hass.async_block_till_done()

    # Make blind_open fail with OSError (which the cover already handles)
    mock_vitrea_client.blind_open = AsyncMock(
        side_effect=OSError("Communication error")
    )

    # Try to open the cover
    await cover.async_open_cover()

    # Check error was logged
    assert "Failed to open cover 03/01" in caplog.text
    assert "Communication error" in caplog.text


async def test_cover_duplicate_prevention(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test that duplicate covers are not created."""

    # Create a real cover entity and add it to runtime_data
    cover = VitreaCover(node="03", key="01", position="050", monitor=mock_vitrea_client)
    cover.hass = hass
    cover.entity_id = "cover.cover_03_01"
    cover._attr_unique_id = "03_01"
    cover.async_write_ha_state = MagicMock()

    # Create proper runtime_data with VitreaRuntimeData dataclass
    init_integration.runtime_data = VitreaRuntimeData(
        client=mock_vitrea_client, covers=[cover], switches=[], timers=[]
    )
    await hass.async_block_till_done()

    # Test that event handling finds the existing cover and updates it
    # instead of creating a duplicate
    initial_cover_count = len(init_integration.runtime_data.covers)

    # Simulate VitreaResponse events for same cover with different positions
    event1 = MagicMock(status=DeviceStatus.BLIND, node="03", key="01", data="050")
    event2 = MagicMock(status=DeviceStatus.BLIND, node="03", key="01", data="075")

    _handle_cover_event(init_integration, event1)
    await hass.async_block_till_done()
    _handle_cover_event(init_integration, event2)
    await hass.async_block_till_done()

    # Should still have only one cover entity
    final_cover_count = len(init_integration.runtime_data.covers)
    assert final_cover_count == initial_cover_count == 1

    # Verify the cover was updated (async_write_ha_state called)
    assert cover.async_write_ha_state.call_count >= 1

    # Verify the position was updated to the latest value
    assert cover._attr_current_cover_position == 75
