"""Test for IPMA component Init."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.ipma.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, MockLocation

from tests.common import MockConfigEntry


async def init_integration(
    hass: HomeAssistant,
    config: dict[str, Any] = None,
    entry_id: str = "1",
    source: str = SOURCE_USER,
) -> MockConfigEntry:
    """Set up the SQL integration in Home Assistant."""
    if not config:
        config = ENTRY_CONFIG

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data=config,
        entry_id=entry_id,
    )

    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        return config_entry


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload an entry."""
    config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED
