"""Tests Starlink time entities."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from starlink_grpc import GrpcError

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

ENTITY_ID = "time.starlink_sleep_start"


@pytest.mark.freeze_time("2026-06-01 12:00:00+00:00")
@pytest.mark.parametrize("sleep_config", [[0, 60, True]], indirect=True)
async def test_unavailable_on_update_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_sleep_config: MagicMock,
) -> None:
    """Test the time entity is unavailable while the coordinator update fails."""
    assert hass.states.get(ENTITY_ID).state == "17:00:00"

    mock_sleep_config.side_effect = GrpcError("error")
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_sleep_config.side_effect = None
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == "17:00:00"
