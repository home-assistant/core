"""Test for Trafikverket Ferry component Init."""

from __future__ import annotations

from unittest.mock import patch

from pytrafikverket.trafikverket_ferry import FerryStop

from homeassistant.components.trafikverket_ferry.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, get_ferries: list[FerryStop]) -> None:
    """Test setup entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="123",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_ferry.coordinator.TrafikverketFerry.async_get_next_ferry_stops",
        return_value=get_ferries,
    ) as mock_tvt_ferry:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(mock_tvt_ferry.mock_calls) == 1


async def test_unload_entry(hass: HomeAssistant, get_ferries: list[FerryStop]) -> None:
    """Test unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
        entry_id="1",
        unique_id="321",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.trafikverket_ferry.coordinator.TrafikverketFerry.async_get_next_ferry_stops",
        return_value=get_ferries,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
