"""Tests for the Sense coordinators."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from sense_energy import SenseAuthenticationException, SenseMFARequiredException

from homeassistant.components.sense.const import DOMAIN, TREND_UPDATE_RATE
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from . import setup_platform
from .const import MONITOR_ID

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "exception",
    [
        SenseAuthenticationException("auth expired"),
        SenseMFARequiredException("auth expired"),
    ],
)
async def test_trend_coordinator_auth_failure(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test that auth errors from the trend coordinator start a reauth flow."""
    await setup_platform(hass, config_entry, Platform.SENSOR)

    mock_sense.update_trend_data.side_effect = exception

    freezer.tick(timedelta(seconds=TREND_UPDATE_RATE))
    async_fire_time_changed(hass, freezer())
    await hass.async_block_till_done()

    state = hass.states.get(f"sensor.sense_{MONITOR_ID}_daily_energy")
    assert state.state == STATE_UNAVAILABLE

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    flow = flows[0]
    assert flow.get("step_id") == "reauth_validate"
    assert flow.get("handler") == DOMAIN
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == config_entry.entry_id
