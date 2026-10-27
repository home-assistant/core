"""Tests for the OVHcloud AI Endpoints integration."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_openai_client.chat.completions.create.reset_mock()
