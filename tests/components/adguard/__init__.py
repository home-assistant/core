"""Tests for the AdGuard Home integration."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    adguard_mock: AsyncGenerator,
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.adguard.AdGuardHome",
        return_value=adguard_mock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
