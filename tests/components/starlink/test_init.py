"""Tests Starlink integration init/unload."""

from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .patchers import (
    HISTORY_STATS_SUCCESS_PATCHER,
    LOCATION_DATA_SUCCESS_PATCHER,
    SLEEP_DATA_SUCCESS_PATCHER,
    STATUS_DATA_FIXTURE,
    STATUS_DATA_SUCCESS_PATCHER,
    STATUS_DATA_TARGET,
)

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)


async def test_successful_entry(hass: HomeAssistant) -> None:
    """Test configuring Starlink."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.runtime_data
        assert entry.runtime_data.data
        assert entry.state is ConfigEntryState.LOADED


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing Starlink."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_restore_cache_with_accumulation(hass: HomeAssistant) -> None:
    """Test Starlink accumulation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )
    entity_id = "sensor.starlink_energy"

    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    entity_id,
                    "",
                ),
                {
                    "native_value": 1,
                    "native_unit_of_measurement": None,
                },
            ),
        ),
    )

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.runtime_data
        assert entry.runtime_data.data

        assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

        await entry.runtime_data.async_refresh()

        assert hass.states.get(entity_id).state == str(1 + 0.00786231368489)

        with patch.object(entry.runtime_data, "always_update", return_value=True):
            await entry.runtime_data.async_refresh()

        assert hass.states.get(entity_id).state == str(1 + 0.01572462736977)


async def test_last_restart_state(hass: HomeAssistant) -> None:
    """Test Starlink last restart state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )
    entity_id = "sensor.starlink_last_restart"
    utc_now = datetime.fromisoformat("2025-10-22T13:31:29+00:00")

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        SLEEP_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
    ):
        with freeze_time(utc_now):
            entry.add_to_hass(hass)

            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

        with patch.object(entry.runtime_data, "always_update", return_value=True):
            status_data = deepcopy(STATUS_DATA_FIXTURE)
            status_data[0]["uptime"] = 804144

            with (
                freeze_time(utc_now + timedelta(seconds=5)),
                patch(STATUS_DATA_TARGET, return_value=status_data),
            ):
                async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
                await hass.async_block_till_done(wait_background_tasks=True)

            assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

            status_data[0]["uptime"] = 804134

            with (
                freeze_time(utc_now + timedelta(seconds=10)),
                patch(STATUS_DATA_TARGET, return_value=status_data),
            ):
                async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
                await hass.async_block_till_done(wait_background_tasks=True)

            assert hass.states.get(entity_id).state == "2025-10-13T06:09:11+00:00"

            status_data[0]["uptime"] = 100

            with (
                freeze_time(utc_now + timedelta(seconds=15)),
                patch(STATUS_DATA_TARGET, return_value=status_data),
            ):
                async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
                await hass.async_block_till_done(wait_background_tasks=True)

            assert hass.states.get(entity_id).state == "2025-10-22T13:30:04+00:00"
