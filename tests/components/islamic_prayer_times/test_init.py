"""Tests for Islamic Prayer Times init."""

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.components.islamic_prayer_times.const import CONF_CALC_METHOD, DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from . import NOW, PRAYER_TIMES

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture(autouse=True)
async def set_utc(hass: HomeAssistant) -> None:
    """Set timezone to UTC."""
    await hass.config.async_set_time_zone("UTC")


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test that Islamic Prayer Times is configured successfully."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Islamic Prayer Times."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_listener(hass: HomeAssistant) -> None:
    """Ensure updating options triggers a coordinator refresh."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    with (
        patch(
            "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
            return_value=PRAYER_TIMES,
        ) as mock_fetch_prayer_times,
        freeze_time(NOW),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Each scheduling run calls this 3 times (yesterday, today, tomorrow)
        assert mock_fetch_prayer_times.call_count == 3
        mock_fetch_prayer_times.reset_mock()

        hass.config_entries.async_update_entry(
            entry, options={CONF_CALC_METHOD: "makkah"}
        )
        await hass.async_block_till_done()
        # Each scheduling run calls this 3 times (yesterday, today, tomorrow)
        assert mock_fetch_prayer_times.call_count == 3


@pytest.mark.parametrize(
    ("object_id", "old_unique_id"),
    [
        (
            "fajer_prayer",
            "Fajr",
        ),
        (
            "dhuhr_prayer",
            "Dhuhr",
        ),
    ],
)
async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    object_id: str,
    old_unique_id: str,
) -> None:
    """Test unique id migration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id=object_id,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id

    with (
        patch(
            "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
            return_value=PRAYER_TIMES,
        ),
        freeze_time(NOW),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{entry.entry_id}-{old_unique_id}"


async def test_migration_from_1_1_to_1_2(hass: HomeAssistant) -> None:
    """Test migrating from version 1.1 to 1.2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
            return_value=PRAYER_TIMES,
        ),
        freeze_time(NOW),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.data == {
        CONF_LATITUDE: hass.config.latitude,
        CONF_LONGITUDE: hass.config.longitude,
    }
    assert entry.minor_version == 2


async def test_update_scheduling(hass: HomeAssistant) -> None:
    """Test that integration schedules update immediately after Islamic midnight."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    with (
        patch(
            "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
            return_value=PRAYER_TIMES,
        ),
        freeze_time(NOW),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

    with patch(
        "prayer_times_calculator_offline.PrayerTimesCalculator.fetch_prayer_times",
        return_value=PRAYER_TIMES,
    ) as mock_fetch_prayer_times:
        midnight_time = dt_util.parse_datetime(PRAYER_TIMES["Midnight"])
        assert midnight_time
        with freeze_time(midnight_time):
            async_fire_time_changed(hass, midnight_time)
            await hass.async_block_till_done()

            mock_fetch_prayer_times.assert_not_called()

        midnight_time += timedelta(seconds=1)
        with freeze_time(midnight_time):
            async_fire_time_changed(hass, midnight_time)
            await hass.async_block_till_done()

            # Each scheduling run calls this 3 times (yesterday, today, tomorrow)
            assert mock_fetch_prayer_times.call_count == 3
