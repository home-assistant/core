"""Tests for setting up the Plexilent integration."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyplexilent import Device, PlexilentAuthError, PlexilentError
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.plexilent.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import DEVICES


async def test_setup_retry_unload(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """Setup retries while the cloud is down, then the entry unloads cleanly."""
    client.devices.side_effect = PlexilentError
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY

    client.devices.side_effect = None
    await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_auth_failed(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """A rejected refresh token fails setup without retrying."""
    client.devices.side_effect = PlexilentAuthError
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert not hass.config_entries.flow.async_progress()


async def test_poll_auth_failed(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A rejected refresh token makes lights unavailable and stops polling."""
    entity_id = "light.gate"
    await setup_integration(hass, entry)
    assert hass.states.is_state(entity_id, STATE_ON)

    client.devices.side_effect = PlexilentAuthError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.devices.await_count == 2
    assert hass.states.is_state(entity_id, STATE_UNAVAILABLE)
    assert not hass.config_entries.flow.async_progress()

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.devices.await_count == 2


async def test_new_device(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device added in the app appears on the next poll."""
    await setup_integration(hass, entry)
    client.devices.return_value = [
        *DEVICES,
        Device(
            id="m:30",
            name="Bed",
            type="ct",
            home="m",
            online=True,
            on=True,
            brightness=50,
            cct=4000,
            cct_min=2700,
            cct_max=6500,
        ),
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 5
    bed = hass.states.get("light.bed")
    assert bed.attributes["color_mode"] == "color_temp"
    assert bed.attributes["color_temp_kelvin"] == 4000
