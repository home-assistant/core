"""Test Script for Fluss+ Initialisation."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: list[Platform] | None = None,
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    if platforms is not None:
        with patch(
            "homeassistant.components.fluss.PLATFORMS",
            platforms,
        ):
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
    else:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
