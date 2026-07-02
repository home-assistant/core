"""Setup/unload tests for the Noonlight integration."""

import httpx
from httpx import Response
import respx

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import STATUS_RE

from tests.common import MockConfigEntry


@respx.mock
async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A reachable probe loads the entry; it then unloads cleanly."""
    respx.get(url__regex=STATUS_RE).mock(return_value=Response(404))

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@respx.mock
async def test_setup_succeeds_even_when_unreachable(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Setup still completes when the API is unreachable (sensor reports off)."""
    respx.get(url__regex=STATUS_RE).mock(side_effect=httpx.ConnectError("down"))

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
