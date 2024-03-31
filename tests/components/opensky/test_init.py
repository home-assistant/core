"""Test OpenSky component setup process."""

from __future__ import annotations

from unittest.mock import AsyncMock

from python_opensky import OpenSkyError
from python_opensky.exceptions import OpenSkyUnauthenticatedError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.opensky import setup_integration


async def test_load_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    opensky_client: AsyncMock,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_load_entry_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    opensky_client: AsyncMock,
) -> None:
    """Test failure while loading."""
    opensky_client.get_states.side_effect = OpenSkyError()
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_entry_authentication_failure(
    hass: HomeAssistant,
    config_entry_authenticated: MockConfigEntry,
    opensky_client: AsyncMock,
) -> None:
    """Test auth failure while loading."""
    opensky_client.authenticate.side_effect = OpenSkyUnauthenticatedError()
    config_entry_authenticated.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(
        config_entry_authenticated.entry_id
    )
    await hass.async_block_till_done()

    assert config_entry_authenticated.state is ConfigEntryState.SETUP_RETRY
