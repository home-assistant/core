"""Tests for the Eufy RoboVac integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robovac: AsyncMock,
) -> None:
    """Set up the Eufy RoboVac integration."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.eufy_robovac.RoboVac",
        return_value=robovac,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
