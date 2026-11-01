"""Tests Starlink time entities."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from starlink_grpc import GrpcError

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .patchers import (
    HISTORY_STATS_SUCCESS_PATCHER,
    LOCATION_DATA_SUCCESS_PATCHER,
    STATUS_DATA_SUCCESS_PATCHER,
)

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "time.starlink_sleep_start"
SLEEP_DATA_TARGET = "homeassistant.components.starlink.coordinator.get_sleep_config"


@pytest.mark.freeze_time("2026-06-01 12:00:00+00:00")
async def test_unavailable_on_update_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the time entity is unavailable while the coordinator update fails."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4:0000"})

    with (
        LOCATION_DATA_SUCCESS_PATCHER,
        STATUS_DATA_SUCCESS_PATCHER,
        HISTORY_STATS_SUCCESS_PATCHER,
        patch(SLEEP_DATA_TARGET, return_value=[0, 60, True]) as mock_sleep,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get(ENTITY_ID).state == "17:00:00"

        mock_sleep.side_effect = GrpcError("error")
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

        mock_sleep.side_effect = None
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get(ENTITY_ID).state == "17:00:00"
