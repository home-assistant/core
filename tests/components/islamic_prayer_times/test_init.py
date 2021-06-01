"""Tests for Islamic Prayer Times init."""

from datetime import timedelta
from unittest.mock import patch

from prayer_times_calculator.exceptions import InvalidResponseError

from homeassistant.components.islamic_prayer_times import (
    DOMAIN,
    IslamicPrayerDataCoordinator,
)
from homeassistant.components.islamic_prayer_times.const import CONF_CALC_METHOD
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    NEW_PRAYER_TIMES,
    NEW_PRAYER_TIMES_TIMESTAMPS,
    NOW,
    PRAYER_TIMES,
    PRAYER_TIMES_TIMESTAMPS,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_successful_config_entry(
    hass: HomeAssistant, legacy_patchable_time
) -> None:
    """Test that Islamic Prayer Times is configured successfully."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_failed(
    hass: HomeAssistant, mock_api, legacy_patchable_time
) -> None:
    """Test Islamic Prayer Times failed due to an error."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    # test request error raising ConfigEntryNotReady
    mock_api.side_effect = InvalidResponseError()

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, legacy_patchable_time) -> None:
    """Test removing Islamic Prayer Times."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data


async def test_updating_options(hass: HomeAssistant) -> None:
    """Test successful update of calc_metho from old entry data."""
    legacy_options = {
        CONF_CALC_METHOD: "isna",
    }
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=legacy_options)
    entry.add_to_hass(hass)

    assert entry.options[CONF_CALC_METHOD] == "isna"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.options[CONF_CALC_METHOD] == "ISNA"


async def test_islamic_prayer_times_timestamp_format(
    hass: HomeAssistant, legacy_patchable_time
) -> None:
    """Test Islamic prayer times timestamp format."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ), patch("homeassistant.util.dt.now", return_value=NOW):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.data[DOMAIN].data == PRAYER_TIMES_TIMESTAMPS


async def test_update(hass: HomeAssistant, legacy_patchable_time) -> None:
    """Test sensors are updated with new prayer times."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
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

        pt_data: IslamicPrayerDataCoordinator = hass.data[DOMAIN]
        assert pt_data.data == PRAYER_TIMES_TIMESTAMPS

        future = pt_data.data["Midnight"] + timedelta(days=1, minutes=1)

        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN].data == NEW_PRAYER_TIMES_TIMESTAMPS
