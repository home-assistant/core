"""Tests for myuplink update module."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_update_states(
    hass: HomeAssistant,
    mock_myuplink_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test update state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("update.gotham_city_firmware")
    assert state is not None
    assert state.state == "off"
