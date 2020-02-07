"""Tests for Islamic Prayer Times init."""

from unittest.mock import patch

import prayer_times_calculator
import pytest

from homeassistant.components import islamic_prayer_times
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro

MOCK_OPTIONS = {islamic_prayer_times.CONF_CALC_METHOD: "makkah"}

PRAYER_TIMES = {
    "Fajr": "06:10",
    "Sunrise": "07:25",
    "Dhuhr": "12:30",
    "Asr": "15:32",
    "Maghrib": "17:35",
    "Isha": "18:53",
    "Midnight": "00:45",
}


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a Islamic Prayer Times."""
    assert await async_setup_component(hass, islamic_prayer_times.DOMAIN, {}) is True
    assert islamic_prayer_times.DOMAIN not in hass.data


async def test_setup_with_config(hass):
    """Test that we import the config and setup the client."""
    config = {
        islamic_prayer_times.DOMAIN: {islamic_prayer_times.CONF_CALC_METHOD: "isna"}
    }
    assert (
        await async_setup_component(hass, islamic_prayer_times.DOMAIN, config) is True
    )


async def test_successful_config_entry(hass):
    """Test that Islamic Prayer Times is configured successfully."""

    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={},)
    entry.add_to_hass(hass)

    assert await islamic_prayer_times.async_setup_entry(hass, entry) is True
    assert entry.options == {
        islamic_prayer_times.CONF_CALC_METHOD: islamic_prayer_times.DEFAULT_CALC_METHOD
    }


async def test_setup_failed(hass):
    """Test Islamic Prayer Times failed due to an error."""

    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={},)
    entry.add_to_hass(hass)

    # test request error raising ConfigEntryNotReady
    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        side_effect=prayer_times_calculator.exceptions.InvalidResponseError(),
    ), pytest.raises(ConfigEntryNotReady):

        await islamic_prayer_times.async_setup_entry(hass, entry)


async def test_unload_entry(hass):
    """Test removing Islamic Prayer Times."""
    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={},)
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries, "async_forward_entry_unload", return_value=mock_coro(True)
    ) as unload_entry:
        assert await islamic_prayer_times.async_setup_entry(hass, entry)

        assert await islamic_prayer_times.async_unload_entry(hass, entry)
        assert unload_entry.call_count == 1
        assert islamic_prayer_times.DOMAIN not in hass.data


async def test_islamic_prayer_times_data_get_prayer_times(hass):
    """Test Islamic prayer times data fetcher."""
    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ):
        config_entry = MockConfigEntry(
            domain=islamic_prayer_times.DOMAIN, data={}, options=MOCK_OPTIONS
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        pt_data = islamic_prayer_times.IslamicPrayerClient(hass, config_entry)
        await pt_data.async_setup()
        assert pt_data.prayer_times_info == PRAYER_TIMES
