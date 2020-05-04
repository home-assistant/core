"""Tests for Islamic Prayer Times init."""

from datetime import timedelta

from prayer_times_calculator.exceptions import InvalidResponseError

from homeassistant import config_entries
from homeassistant.components import islamic_prayer_times
from homeassistant.setup import async_setup_component

from . import (
    NEW_PRAYER_TIMES,
    NEW_PRAYER_TIMES_TIMESTAMPS,
    NOW,
    PRAYER_TIMES,
    PRAYER_TIMES_TIMESTAMPS,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_with_config(hass):
    """Test that we import the config and setup the client."""
    config = {
        islamic_prayer_times.DOMAIN: {islamic_prayer_times.CONF_CALC_METHOD: "isna"}
    }
    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ):
        assert (
            await async_setup_component(hass, islamic_prayer_times.DOMAIN, config)
            is True
        )


async def test_successful_config_entry(hass):
    """Test that Islamic Prayer Times is configured successfully."""

    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={},)
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

        assert entry.state == config_entries.ENTRY_STATE_LOADED
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
        side_effect=InvalidResponseError(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == config_entries.ENTRY_STATE_SETUP_RETRY


async def test_unload_entry(hass):
    """Test removing Islamic Prayer Times."""
    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={},)
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
        assert islamic_prayer_times.DOMAIN not in hass.data


async def test_islamic_prayer_times_timestamp_format(hass):
    """Test Islamic prayer times timestamp format."""
    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ), patch("homeassistant.util.dt.now", return_value=NOW):

        await hass.config_entries.async_setup(entry.entry_id)

        assert (
            hass.data[islamic_prayer_times.DOMAIN].prayer_times_info
            == PRAYER_TIMES_TIMESTAMPS
        )


async def test_update(hass):
    """Test sensors are updated with new prayer times."""
    entry = MockConfigEntry(domain=islamic_prayer_times.DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times"
    ) as FetchPrayerTimes, patch("homeassistant.util.dt.now", return_value=NOW):
        FetchPrayerTimes.side_effect = [
            PRAYER_TIMES,
            PRAYER_TIMES,
            NEW_PRAYER_TIMES,
        ]

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        pt_data = hass.data[islamic_prayer_times.DOMAIN]
        assert pt_data.prayer_times_info == PRAYER_TIMES_TIMESTAMPS

        future = pt_data.prayer_times_info["Midnight"] + timedelta(days=1, minutes=1)

        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert (
            hass.data[islamic_prayer_times.DOMAIN].prayer_times_info
            == NEW_PRAYER_TIMES_TIMESTAMPS
        )
