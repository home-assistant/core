"""The tests for the Landis+Gyr Heat Meter sensor platform."""
import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import serial
from syrupy import SnapshotAssertion
from ultraheat_api.response import HeatMeterResponse

from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.components.landisgyr_heat_meter.const import DOMAIN, POLLING_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

API_HEAT_METER_SERVICE = (
    "homeassistant.components.landisgyr_heat_meter.ultraheat_api.HeatMeterService"
)

MOCK_RESPONSE_GJ = {
    "model": "abc",
    "heat_usage_gj": 123.0,
    "heat_usage_mwh": None,
    "volume_usage_m3": 456.0,
    "ownership_number": "123a",
    "volume_previous_year_m3": 450.0,
    "heat_previous_year_gj": 111.0,
    "heat_previous_year_mwh": None,
    "error_number": "0",
    "device_number": "abc1",
    "measurement_period_minutes": 60,
    "power_max_kw": 22.1,
    "power_max_previous_year_kw": 22.4,
    "flowrate_max_m3ph": 0.744,
    "flow_temperature_max_c": 98.5,
    "flowrate_max_previous_year_m3ph": 0.743,
    "return_temperature_max_c": 96.1,
    "flow_temperature_max_previous_year_c": 98.4,
    "return_temperature_max_previous_year_c": 96.2,
    "operating_hours": 115575,
    "fault_hours": 5,
    "fault_hours_previous_year": 5,
    "yearly_set_day": "01-01",
    "monthly_set_day": "01",
    "meter_date_time": dt_util.as_utc(datetime.datetime(2022, 5, 19, 19, 41, 17)),
    "measuring_range_m3ph": 1.5,
    "settings_and_firmware": "0 1 0 0000 CECV CECV 1 5.16 5.16 F 101008 040404 08 0",
    "flow_hours": 30242,
    "raw_response": "6.8(0328.872*GJ)6.26(03329.68*m3)9.21(66153690)",
}

MOCK_RESPONSE_MWH = {
    "model": "abc",
    "heat_usage_gj": None,
    "heat_usage_mwh": 123.0,
    "volume_usage_m3": 456.0,
    "ownership_number": "123a",
    "volume_previous_year_m3": 450.0,
    "heat_previous_year_gj": None,
    "heat_previous_year_mwh": 111.0,
    "error_number": "0",
    "device_number": "abc1",
    "measurement_period_minutes": 60,
    "power_max_kw": 22.1,
    "power_max_previous_year_kw": 22.4,
    "flowrate_max_m3ph": 0.744,
    "flow_temperature_max_c": 98.5,
    "flowrate_max_previous_year_m3ph": 0.743,
    "return_temperature_max_c": 96.1,
    "flow_temperature_max_previous_year_c": 98.4,
    "return_temperature_max_previous_year_c": 96.2,
    "operating_hours": 115575,
    "fault_hours": 5,
    "fault_hours_previous_year": 5,
    "yearly_set_day": "01-01",
    "monthly_set_day": "01",
    "meter_date_time": dt_util.as_utc(datetime.datetime(2022, 5, 19, 19, 41, 17)),
    "measuring_range_m3ph": 1.5,
    "settings_and_firmware": "0 1 0 0000 CECV CECV 1 5.16 5.16 F 101008 040404 08 0",
    "flow_hours": 30242,
    "raw_response": "6.8(0328.872*MWh)6.26(03329.68*m3)9.21(66153690)",
}


@pytest.mark.parametrize(
    "mock_heat_meter_response",
    [
        MOCK_RESPONSE_GJ,
        MOCK_RESPONSE_MWH,
    ],
)
@patch(API_HEAT_METER_SERVICE)
async def test_create_sensors(
    mock_heat_meter,
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_heat_meter_response,
) -> None:
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)
    mock_entry.add_to_hass(hass)

    mock_heat_meter_response = HeatMeterResponse(**mock_heat_meter_response)

    mock_heat_meter().read.return_value = mock_heat_meter_response

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.states.async_all() == snapshot


@patch(API_HEAT_METER_SERVICE)
async def test_exception_on_polling(
    mock_heat_meter, hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)
    mock_entry.add_to_hass(hass)

    # First setup normally
    mock_heat_meter_response = HeatMeterResponse(**MOCK_RESPONSE_GJ)

    mock_heat_meter().read.return_value = mock_heat_meter_response

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()

    # check if initial setup succeeded
    state = hass.states.get("sensor.heat_meter_heat_usage_gj")
    assert state
    assert state.state == "123.0"

    # Now 'disable' the connection and wait for polling and see if it fails
    mock_heat_meter().read.side_effect = serial.SerialException
    freezer.tick(POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.heat_meter_heat_usage_gj")
    assert state.state == STATE_UNAVAILABLE

    # # Now 'enable' and see if next poll succeeds
    mock_heat_meter_response = HeatMeterResponse(**MOCK_RESPONSE_GJ)
    mock_heat_meter_response.heat_usage_gj += 1

    mock_heat_meter().read.return_value = mock_heat_meter_response
    mock_heat_meter().read.side_effect = None
    freezer.tick(POLLING_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.heat_meter_heat_usage_gj")
    assert state
    assert state.state == "124.0"
