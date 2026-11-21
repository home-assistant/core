"""Tests for the NRGkick integration."""

from collections.abc import Iterable
from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: Iterable[Platform] | None = None,
) -> None:
    """Set up the component for tests."""
    config_entry.add_to_hass(hass)

    if platforms is None:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return

    with patch("homeassistant.components.nrgkick.PLATFORMS", list(platforms)):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
