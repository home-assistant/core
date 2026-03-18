"""Tests for the Velux cover platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_CLOSED, STATE_OPEN, Platform
from homeassistant.core import HomeAssistant

from . import update_callback_entity

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_module")
async def test_cover_closed(
    hass: HomeAssistant,
    mock_window: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the cover closed state."""

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.velux.PLATFORMS", [Platform.COVER]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    test_entity_id = "cover.test_window"

    # Initial state should be open
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_OPEN

    # Update mock window position to closed percentage
    mock_window.position.position_percent = 100
    # Also directly set position to closed, so this test should
    # continue to be green after the lib is fixed
    mock_window.position.closed = True

    # Trigger entity state update via registered callback
    await update_callback_entity(hass, mock_window)

    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_CLOSED
