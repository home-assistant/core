"""Test Essent coordinator scheduling without disabling fixtures.

This module tests the scheduling logic properly using HA's time utilities.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.essent.const import API_ENDPOINT, DOMAIN
from homeassistant.components.essent.coordinator import EssentDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
)

# Don't use the autouse fixture that disables scheduling
pytestmark = [
    pytest.mark.freeze_time("2025-11-16 12:00:00+01:00"),
]


@pytest.fixture
async def setup_timezone(hass: HomeAssistant) -> None:
    """Set up timezone for scheduling tests."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")


@pytest.fixture
def mock_random_offset():
    """Mock random offset to be predictable."""
    with patch(
        "homeassistant.components.essent.coordinator.random.randint", return_value=15
    ):
        yield


async def test_start_schedules_activates_both_schedulers(
    hass: HomeAssistant,
    setup_timezone,
    mock_random_offset,
    aioclient_mock,
) -> None:
    """Test that start_schedules activates both API and listener schedulers."""
    essent_api_response = load_json_object_fixture("essent_api_response.json", DOMAIN)
    aioclient_mock.get(API_ENDPOINT, json=essent_api_response)

    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    # Set up integration properly
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    # Schedules should be active after setup
    assert coordinator.api_refresh_scheduled
    assert coordinator.listener_tick_scheduled
    assert coordinator.api_fetch_minute_offset == 15


async def test_start_schedules_respects_disable_polling(
    hass: HomeAssistant,
    setup_timezone,
    mock_random_offset,
    aioclient_mock,
) -> None:
    """Test that scheduling respects pref_disable_polling."""
    essent_api_response = load_json_object_fixture("essent_api_response.json", DOMAIN)
    aioclient_mock.get(API_ENDPOINT, json=essent_api_response)

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
    assert not coordinator.api_refresh_scheduled
    assert not coordinator.listener_tick_scheduled


async def test_listener_tick_fires_on_the_hour(
    hass: HomeAssistant,
    setup_timezone,
    mock_random_offset,
    aioclient_mock,
    freezer,
) -> None:
    """Test that listener tick fires exactly on the hour."""
    essent_api_response = load_json_object_fixture("essent_api_response.json", DOMAIN)
    aioclient_mock.get(API_ENDPOINT, json=essent_api_response)

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
    mock_random_offset,
    aioclient_mock,
    freezer,
) -> None:
    """Test that API refresh fires at the random minute offset."""
    essent_api_response = load_json_object_fixture("essent_api_response.json", DOMAIN)
    aioclient_mock.get(API_ENDPOINT, json=essent_api_response)

    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    initial_call_count = aioclient_mock.call_count

    # Move to next hour + offset (13:15:00)
    next_trigger = dt_util.utcnow().replace(
        minute=0, second=0, microsecond=0
    ) + timedelta(hours=1, minutes=15)
    freezer.move_to(next_trigger)
    async_fire_time_changed(hass, next_trigger)
    await hass.async_block_till_done()

    # API should have been called again
    assert aioclient_mock.call_count > initial_call_count


async def test_shutdown_cancels_schedules(
    hass: HomeAssistant,
    setup_timezone,
    mock_random_offset,
    aioclient_mock,
) -> None:
    """Test that shutdown properly cancels scheduled tasks."""
    essent_api_response = load_json_object_fixture("essent_api_response.json", DOMAIN)
    aioclient_mock.get(API_ENDPOINT, json=essent_api_response)

    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    # Schedules should be active
    assert coordinator.api_refresh_scheduled
    assert coordinator.listener_tick_scheduled

    # Unload the integration (triggers shutdown)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Schedules should be cancelled
    assert not coordinator.api_refresh_scheduled
    assert not coordinator.listener_tick_scheduled


async def test_schedule_reschedules_itself(
    hass: HomeAssistant,
    setup_timezone,
    mock_random_offset,
    aioclient_mock,
    freezer,
) -> None:
    """Test that schedules reschedule themselves after firing."""
    essent_api_response = load_json_object_fixture("essent_api_response.json", DOMAIN)
    aioclient_mock.get(API_ENDPOINT, json=essent_api_response)

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
    ) + timedelta(hours=1, minutes=15)
    freezer.move_to(next_trigger)
    async_fire_time_changed(hass, next_trigger)
    await hass.async_block_till_done()

    # Schedule should still be active (rescheduled)
    assert coordinator.api_refresh_scheduled
