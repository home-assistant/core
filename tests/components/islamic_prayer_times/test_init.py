"""Tests for Islamic Prayer Times init."""

from freezegun import freeze_time
import requests_mock

from homeassistant import config_entries
from homeassistant.components import islamic_prayer_times
from homeassistant.core import HomeAssistant

from . import NOW, REQUEST_URL

from tests.common import MockConfigEntry


@freeze_time(NOW)
async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test that Islamic Prayer Times is configured successfully."""

    entry = MockConfigEntry(
        domain=islamic_prayer_times.DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_setup_failed(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test Islamic Prayer Times failed due to an error."""

    entry = MockConfigEntry(
        domain=islamic_prayer_times.DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    # test request error raising ConfigEntryNotReady
    requests_mock.get(REQUEST_URL, status_code=400)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY


@freeze_time(NOW)
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Islamic Prayer Times."""
    entry = MockConfigEntry(
        domain=islamic_prayer_times.DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert islamic_prayer_times.DOMAIN not in hass.data
