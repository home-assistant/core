"""Tests for the samsungtv component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_samsungtv_entry(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> ConfigEntry:
    """Set up mock Samsung TV from config entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        entry_id="123456",
        unique_id="be9554b9-c9fb-41f4-8920-22da015376a4",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
