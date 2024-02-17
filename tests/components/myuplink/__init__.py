"""Tests for the myuplink integration."""
from unittest.mock import patch

from homeassistant.components.myuplink import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)


async def setup_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    platform: str | None = None,
) -> MockConfigEntry:
    """Set up one or all platforms."""
    config_entry = mock_config_entry
    config_entry.add_to_hass(hass)

    if platform:
        with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", [platform]):
            assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    return config_entry
