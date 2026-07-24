"""Tests for the slide_local integration."""

from typing import Any
from unittest.mock import patch

from homeassistant.components.slide_local.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


async def setup_platform(
    hass: HomeAssistant, config_entry: MockConfigEntry, platforms: list[Platform]
) -> MockConfigEntry:
    """Set up the slide local integration."""
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.slide_local.PLATFORMS", platforms):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def get_data() -> dict[str, Any]:
    """Return the default state data.

    The coordinator mutates the returned API data, so we can't return a glocal dict.
    """
    return load_json_object_fixture("slide_1.json", DOMAIN)
