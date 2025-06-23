"""Tests for the coordinator."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import requests_mock

from homeassistant.components.vesync.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import (
    mock_air_purifier_400s_update_response,
    mock_device_response,
    mock_multiple_device_responses,
    mock_outlet_energy_response,
)

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_entity_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test Vesync coordinator data update.

    This test sets up a single device `Air Purifier 400s` and then updates it via the coordinator.
    """

    config_data = {CONF_PASSWORD: "username", CONF_USERNAME: "password"}
    config_entry = MockConfigEntry(
        data=config_data,
        domain=DOMAIN,
        unique_id="vesync_unique_id_1",
        entry_id="1",
    )

    mock_multiple_device_responses(requests_mock, ["Air Purifier 400s", "Outlet"])

    expected_entities = [
        # From "Air Purifier 400s"
        "fan.air_purifier_400s",
        "sensor.air_purifier_400s_filter_lifetime",
        "sensor.air_purifier_400s_air_quality",
        "sensor.air_purifier_400s_pm2_5",
        # From Outlet
        "switch.outlet",
        "sensor.outlet_current_power",
        "sensor.outlet_energy_use_today",
        "sensor.outlet_energy_use_weekly",
        "sensor.outlet_energy_use_monthly",
        "sensor.outlet_energy_use_yearly",
        "sensor.outlet_current_voltage",
    ]

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    for entity_id in expected_entities:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    assert hass.states.get("sensor.air_purifier_400s_air_quality").state == "5"
    assert hass.states.get("sensor.outlet_current_voltage").state == "120.0"
    assert hass.states.get("sensor.outlet_energy_use_weekly").state == "0"

    # Update the mock responses
    mock_air_purifier_400s_update_response(requests_mock)
    mock_outlet_energy_response(requests_mock, "Outlet", {"totalEnergy": 2.2})
    mock_device_response(requests_mock, "Outlet", {"voltage": 129})

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(True)

    assert hass.states.get("sensor.air_purifier_400s_air_quality").state == "15"
    assert hass.states.get("sensor.outlet_current_voltage").state == "129.0"

    # Test energy update
    # pyvesync only updates energy parameters once every 6 hours.
    freezer.tick(timedelta(hours=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(True)

    assert hass.states.get("sensor.air_purifier_400s_air_quality").state == "15"
    assert hass.states.get("sensor.outlet_current_voltage").state == "129.0"
    assert hass.states.get("sensor.outlet_energy_use_weekly").state == "2.2"
