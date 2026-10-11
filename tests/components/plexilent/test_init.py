"""Tests for setting up the Plexilent integration."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyplexilent import Device, PlexilentAuthError, PlexilentError

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.plexilent.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import DEVICES

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_retry_unload_remove(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """Setup retries while the cloud is down; removing the entry revokes the link."""
    client.devices.side_effect = PlexilentError
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY

    client.devices.side_effect = None
    await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    await hass.config_entries.async_remove(entry.entry_id)
    client.unlink.assert_awaited_once()


async def test_setup_auth_failed(
    hass: HomeAssistant, client: MagicMock, entry: MockConfigEntry
) -> None:
    """A rejected login at setup starts reauthentication."""
    client.devices.side_effect = PlexilentAuthError
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [f["step_id"] for f in hass.config_entries.flow.async_progress()] == [
        "reauth_confirm"
    ]


async def test_new_device_then_auth_failure(
    hass: HomeAssistant,
    client: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device added in the app appears on the next poll; a revoked link asks to sign in."""
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

    client.devices.side_effect = PlexilentAuthError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [f["step_id"] for f in hass.config_entries.flow.async_progress()] == [
        "reauth_confirm"
    ]
