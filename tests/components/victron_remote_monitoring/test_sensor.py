"""Tests for the VRM Forecasts sensors."""

from __future__ import annotations

import pytest

from homeassistant.components.victron_remote_monitoring.const import DOMAIN
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import CONST_FORECAST_RECORDS


async def test_sensors_states_and_units(
    hass: HomeAssistant, init_integration, mock_config_entry
) -> None:
    """Verify energy sensors report expected values and units."""
    # Yesterday total: first two records in fixture
    yesterday_total = CONST_FORECAST_RECORDS[0][1] + CONST_FORECAST_RECORDS[1][1]
    # Today total: two "today" records
    today_total = CONST_FORECAST_RECORDS[2][1] + CONST_FORECAST_RECORDS[3][1]
    # Today remaining (after 12:01): only the 13:00 record counts
    today_remaining = CONST_FORECAST_RECORDS[3][1]
    # Tomorrow total: two "tomorrow" records
    tomorrow_total = CONST_FORECAST_RECORDS[4][1] + CONST_FORECAST_RECORDS[5][1]
    ent_reg = er.async_get(hass)
    site_id = mock_config_entry.data["site_id"]

    # Sensors expose Wh as native with suggested kWh; HA may convert to kWh in state
    # Verify state is reported in kWh and values divided by 1000
    for key, expected in (
        ("energy_production_estimate_yesterday", yesterday_total),
        ("energy_production_estimate_today", today_total),
        ("energy_production_estimate_today_remaining", today_remaining),
        ("energy_production_estimate_tomorrow", tomorrow_total),
        ("energy_consumption_estimate_yesterday", yesterday_total),
        ("energy_consumption_estimate_today", today_total),
        ("energy_consumption_estimate_today_remaining", today_remaining),
        ("energy_consumption_estimate_tomorrow", tomorrow_total),
    ):
        unique_id = f"{key}_{site_id}"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, key
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert (
            state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR
        )
        assert float(state.state) == pytest.approx(expected / 1000.0)


async def test_sensors_timestamps(
    hass: HomeAssistant, init_integration, mock_config_entry
) -> None:
    """Verify timestamp sensors expose ISO-formatted times in state."""
    ent_reg = er.async_get(hass)
    site_id = mock_config_entry.data["site_id"]

    # Peak times are at 12:00 for each day per fixture data
    for key in (
        "power_highest_peak_time_yesterday",
        "power_highest_peak_time_today",
        "power_highest_peak_time_tomorrow",
        "consumption_highest_peak_time_yesterday",
        "consumption_highest_peak_time_today",
        "consumption_highest_peak_time_tomorrow",
    ):
        unique_id = f"{key}_{site_id}"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, key
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        # Basic shape check
        assert "T" in state.state and state.state.endswith("+00:00")


async def test_unique_ids(
    hass: HomeAssistant, init_integration, mock_config_entry
) -> None:
    """Ensure unique_id format includes key and site id."""
    ent_reg = er.async_get(hass)
    site_id = mock_config_entry.data["site_id"]

    # Check a couple of representative sensors
    for key in (
        "energy_production_estimate_today",
        "consumption_highest_peak_time_today",
    ):
        unique_id = f"{key}_{site_id}"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, key
        entity = ent_reg.async_get(entity_id)
        assert entity is not None, entity_id
        assert entity.unique_id == unique_id
