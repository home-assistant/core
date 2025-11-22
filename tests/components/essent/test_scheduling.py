"""Test Essent coordinator scheduling without disabling fixtures.

This module tests the scheduling logic properly using HA's time utilities.
"""

from __future__ import annotations

from datetime import timedelta
import pytest

from homeassistant.components.essent.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.components.essent.coordinator import EssentDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

# Don't use the autouse fixture that disables scheduling
pytestmark = [
    pytest.mark.freeze_time("2025-11-16 12:00:00+01:00"),
]


@pytest.fixture
async def setup_timezone(hass: HomeAssistant) -> None:
    """Set up timezone for scheduling tests."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")


async def test_start_schedules_activates_both_schedulers(
    hass: HomeAssistant,
    setup_timezone,
    patch_essent_client,
) -> None:
    """Test that listener scheduler activates and polling is configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    # Set up integration properly
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    # Listener schedule should be active after setup
    assert coordinator.listener_tick_scheduled
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_start_schedules_respects_disable_polling(
    hass: HomeAssistant,
    setup_timezone,
    patch_essent_client,
) -> None:
    """Test that scheduling respects pref_disable_polling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=DOMAIN,
        pref_disable_polling=True,
    )
    entry.add_to_hass(hass)

    # Set up integration
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    # Schedules should NOT be active when polling is disabled
    assert not coordinator.listener_tick_scheduled
    assert coordinator.update_interval is None


async def test_listener_tick_fires_on_the_hour(
    hass: HomeAssistant,
    setup_timezone,
    freezer,
) -> None:
    """Test that listener tick fires exactly on the hour."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    # Track listener updates
    listener_call_count = 0

    def listener():
        nonlocal listener_call_count
        listener_call_count += 1

    coordinator.async_add_listener(listener)

    # Move to next hour boundary (13:00:00)
    next_hour = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )
    freezer.move_to(next_hour)
    async_fire_time_changed(hass, next_hour)
    await hass.async_block_till_done()

    # Listener should have been called
    assert listener_call_count == 1


async def test_api_refresh_fires_at_offset(
    hass: HomeAssistant,
    setup_timezone,
    patch_essent_client,
    freezer,
) -> None:
    """Test that API refresh fires on schedule."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    initial_call_count = patch_essent_client.async_get_prices.call_count

    # Move to next hour (13:00:00) since coordinator uses update_interval
    next_trigger = dt_util.utcnow().replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1)
    freezer.move_to(next_trigger)
    async_fire_time_changed(hass, next_trigger)
    await hass.async_block_till_done()

    # API should have been called again
    assert patch_essent_client.async_get_prices.call_count > initial_call_count


async def test_shutdown_cancels_schedules(
    hass: HomeAssistant,
    setup_timezone,
    patch_essent_client,
) -> None:
    """Test that shutdown properly cancels scheduled tasks."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    # Schedules should be active
    assert coordinator.listener_tick_scheduled

    # Unload the integration (triggers shutdown)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Schedules should be cancelled
    assert not coordinator.listener_tick_scheduled


async def test_schedule_reschedules_itself(
    hass: HomeAssistant,
    setup_timezone,
    freezer,
) -> None:
    """Test that schedules reschedule themselves after firing."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    # Fire listener tick
    next_hour = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )
    freezer.move_to(next_hour)
    async_fire_time_changed(hass, next_hour)
    await hass.async_block_till_done()

    # Schedule should still be active (rescheduled)
    assert coordinator.listener_tick_scheduled

    # Fire API refresh
    next_trigger = dt_util.utcnow().replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1)
    freezer.move_to(next_trigger)
    async_fire_time_changed(hass, next_trigger)
    await hass.async_block_till_done()


async def test_listener_schedule_replaces_existing_unsub(
    hass: HomeAssistant,
    setup_timezone,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ensure listener scheduling cancels the previous callback."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data
    cancelled: list[str] = []

    def fake_unsub() -> None:
        cancelled.append("listener_cancelled")

    def fake_track(_hass, _cb, when):
        return lambda: cancelled.append("new_listener_cancelled")

    coordinator._unsub_listener = fake_unsub
    monkeypatch.setattr(
        "homeassistant.components.essent.coordinator.async_track_point_in_utc_time",
        fake_track,
    )

    coordinator._schedule_listener_tick()

    assert "listener_cancelled" in cancelled
