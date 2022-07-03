"""Tests for the SolarEdge coordinator services."""
from unittest.mock import patch

from homeassistant.components.solaredge.const import (
    CONF_SITE_ID,
    DEFAULT_NAME,
    DOMAIN,
    OVERVIEW_UPDATE_DELAY,
    SENSOR_TYPES,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

SITE_ID = "1a2b3c4d5e6f7g8h"
API_KEY = "a1b2c3d4e5f6g7h8"


@patch("homeassistant.components.solaredge.Solaredge")
async def test_solaredgeoverviewdataservice_energy_values_validity(
    mock_solaredge, hass: HomeAssistant
):
    """Test overview energy data validity."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME, CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )
    mock_solaredge().get_details.return_value = {"details": {"status": "active"}}
    mock_config_entry.add_to_hass(hass)
    for description in SENSOR_TYPES:
        description.entity_registry_enabled_default = True

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Valid energy values update
    mock_overview_data = {
        "overview": {
            "lifeTimeData": {"energy": 100000},
            "lastYearData": {"energy": 50000},
            "lastMonthData": {"energy": 10000},
            "lastDayData": {"energy": 0.0},
            "currentPower": {"power": 0.0},
        }
    }
    mock_solaredge().get_overview.return_value = mock_overview_data
    async_fire_time_changed(hass, dt_util.utcnow() + OVERVIEW_UPDATE_DELAY)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lifeTimeData"]["energy"])

    # Invalid energy values, lifeTimeData energy is lower than last year, month or day.
    mock_overview_data["overview"]["lifeTimeData"]["energy"] = 0
    mock_solaredge().get_overview.return_value = mock_overview_data
    async_fire_time_changed(hass, dt_util.utcnow() + OVERVIEW_UPDATE_DELAY)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == STATE_UNKNOWN

    # New valid energy values update
    mock_overview_data["overview"]["lifeTimeData"]["energy"] = 100001
    mock_solaredge().get_overview.return_value = mock_overview_data
    async_fire_time_changed(hass, dt_util.utcnow() + OVERVIEW_UPDATE_DELAY)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lifeTimeData"]["energy"])

    # Invalid energy values, lastYearData energy is lower than last month or day.
    mock_overview_data["overview"]["lastYearData"]["energy"] = 0
    mock_solaredge().get_overview.return_value = mock_overview_data
    async_fire_time_changed(hass, dt_util.utcnow() + OVERVIEW_UPDATE_DELAY)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solaredge_energy_this_year")
    assert state
    assert state.state == STATE_UNKNOWN
    # Check that the valid lastMonthData is still available
    state = hass.states.get("sensor.solaredge_energy_this_month")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lastMonthData"]["energy"])

    # All zero energy values should also be valid.
    mock_overview_data["overview"]["lifeTimeData"]["energy"] = 0.0
    mock_overview_data["overview"]["lastYearData"]["energy"] = 0.0
    mock_overview_data["overview"]["lastMonthData"]["energy"] = 0.0
    mock_overview_data["overview"]["lastDayData"]["energy"] = 0.0
    mock_solaredge().get_overview.return_value = mock_overview_data
    async_fire_time_changed(hass, dt_util.utcnow() + OVERVIEW_UPDATE_DELAY)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.solaredge_lifetime_energy")
    assert state
    assert state.state == str(mock_overview_data["overview"]["lifeTimeData"]["energy"])
