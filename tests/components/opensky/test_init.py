"""Test OpenSky component setup process."""
from __future__ import annotations

from unittest.mock import patch

from python_opensky import OpenSkyError

from homeassistant.components.opensky.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    state = hass.states.get("sensor.opensky")
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.opensky")
    assert not state


async def test_load_entry_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test failure while loading."""
    config_entry.add_to_hass(hass)
    with patch(
        "python_opensky.OpenSky.get_states",
        side_effect=OpenSkyError(),
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state == ConfigEntryState.SETUP_RETRY
