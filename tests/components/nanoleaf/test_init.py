"""Tests for the Nanoleaf integration init."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_without_event_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
) -> None:
    """Test setup entry when device does not support events."""
    mock_nanoleaf.supports_events = False
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nanoleaf.listen_events.assert_not_called()


async def test_setup_entry_with_event_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
) -> None:
    """Test setup entry when device supports events."""
    mock_nanoleaf.supports_events = True
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nanoleaf.listen_events.assert_called_once()
