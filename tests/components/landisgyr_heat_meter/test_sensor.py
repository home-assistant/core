"""The tests for the Landis+Gyr Heat Meter sensor platform."""
from dataclasses import dataclass
import datetime
from unittest.mock import patch

import serial

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.landisgyr_heat_meter.const import DOMAIN, POLLING_INTERVAL
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

API_HEAT_METER_SERVICE = (
    "homeassistant.components.landisgyr_heat_meter.ultraheat_api.HeatMeterService"
)


@dataclass
class MockHeatMeterResponse:
    """Mock for HeatMeterResponse."""

    heat_usage_gj: float
    heat_usage_mwh: float
    volume_usage_m3: float
    heat_previous_year_gj: float
    heat_previous_year_mwh: float
    device_number: str
    meter_date_time: datetime.datetime


@patch(API_HEAT_METER_SERVICE)
async def test_sensors_gj(mock_heat_meter, hass):
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
        "energy_unit": "GJ",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    mock_heat_meter_response = MockHeatMeterResponse(
        heat_usage_gj=123.0,
        heat_usage_mwh=None,
        volume_usage_m3=456.0,
        heat_previous_year_gj=111.0,
        heat_previous_year_mwh=None,
        device_number="devicenr_789",
        meter_date_time=dt_util.as_utc(datetime.datetime(2022, 5, 19, 19, 41, 17)),
    )

    mock_heat_meter().read.return_value = mock_heat_meter_response

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.heat_meter_heat_usage_gj"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # check if the right number of attributes have been created
    assert len(hass.states.async_all()) == 25
    entity_reg = entity_registry.async_get(hass)

    state = hass.states.get("sensor.heat_meter_heat_usage_gj")
    assert state
    assert state.state == "123.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.GIGA_JOULE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY

    state = hass.states.get("sensor.heat_meter_heat_usage")
    assert not state

    state = hass.states.get("sensor.heat_meter_heat_previous_year_gj")
    assert state
    assert state.state == "111.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.GIGA_JOULE

    state = hass.states.get("sensor.heat_meter_heat_previous_year")
    assert not state

    state = hass.states.get("sensor.heat_meter_volume_usage")
    assert state
    assert state.state == "456.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.CUBIC_METERS
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL

    state = hass.states.get("sensor.heat_meter_device_number")
    assert state
    assert state.state == "devicenr_789"
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    entity_registry_entry = entity_reg.async_get("sensor.heat_meter_device_number")
    assert entity_registry_entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.heat_meter_meter_date_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    entity_registry_entry = entity_reg.async_get("sensor.heat_meter_meter_date_time")
    assert entity_registry_entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.heat_meter_flowrate_max_m3ph")
    assert not state


@patch(API_HEAT_METER_SERVICE)
async def test_sensors_mwh(mock_heat_meter, hass):
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    mock_heat_meter_response = MockHeatMeterResponse(
        heat_usage_gj=None,
        heat_usage_mwh=123.0,
        volume_usage_m3=456.0,
        heat_previous_year_gj=None,
        heat_previous_year_mwh=111.0,
        device_number="devicenr_789",
        meter_date_time=dt_util.as_utc(datetime.datetime(2022, 5, 19, 19, 41, 17)),
    )

    mock_heat_meter().read.return_value = mock_heat_meter_response

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "sensor.heat_meter_heat_usage"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 25

    state = hass.states.get("sensor.heat_meter_heat_usage")
    assert state
    assert state.state == "123.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.MEGA_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY

    state = hass.states.get("sensor.heat_meter_heat_previous_year")
    assert state
    assert state.state == "111.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.MEGA_WATT_HOUR

    state = hass.states.get("sensor.heat_meter_heat_usage_gj")
    assert not state

    state = hass.states.get("sensor.heat_meter_heat_previous_year_gj")
    assert not state


@patch(API_HEAT_METER_SERVICE)
async def test_determine_gj_from_data(mock_heat_meter, hass):
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    mock_heat_meter_response = MockHeatMeterResponse(
        heat_usage_gj=123.0,
        heat_usage_mwh=None,
        volume_usage_m3=456.0,
        heat_previous_year_gj=111.0,
        heat_previous_year_mwh=None,
        device_number="devicenr_789",
        meter_date_time=dt_util.as_utc(datetime.datetime(2022, 5, 19, 19, 41, 17)),
    )

    mock_heat_meter().read.return_value = mock_heat_meter_response

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()

    # check if the right number of attributes have been created
    assert len(hass.states.async_all()) == 25

    state = hass.states.get("sensor.heat_meter_heat_usage_gj")
    assert state
    assert state.state == "123.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.GIGA_JOULE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY


@patch(API_HEAT_METER_SERVICE)
async def test_exception_during_setup(mock_heat_meter, hass):
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
        "energy_unit": "MWh",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)
    mock_heat_meter().read.side_effect = serial.serialutil.SerialException
    mock_heat_meter.reset_mock()
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()

    mock_heat_meter.assert_called_once()

    # check if no attributes have been created
    assert len(hass.states.async_all()) == 0


@patch(API_HEAT_METER_SERVICE)
async def test_exception_on_polling(mock_heat_meter, hass):
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
        "energy_unit": "MWh",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)
    mock_entry.add_to_hass(hass)

    # First setup normally
    mock_heat_meter_response = MockHeatMeterResponse(
        heat_usage_gj=None,
        heat_usage_mwh=123.0,
        volume_usage_m3=456.0,
        heat_previous_year_gj=None,
        heat_previous_year_mwh=111.0,
        device_number="devicenr_789",
        meter_date_time=dt_util.as_utc(datetime.datetime(2022, 5, 19, 19, 41, 17)),
    )
    mock_heat_meter().read.return_value = mock_heat_meter_response

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    await hass.async_block_till_done()

    # check if initial setup succeeded
    assert len(hass.states.async_all()) == 25
    state = hass.states.get("sensor.heat_meter_heat_previous_year")
    assert state
    assert state.state == "111.0"

    # Now 'disable' the connection and wait for polling
    mock_heat_meter.reset_mock()
    mock_heat_meter().read.side_effect = serial.serialutil.SerialException
    async_fire_time_changed(hass, dt_util.utcnow() + POLLING_INTERVAL)
    await hass.async_block_till_done()
    mock_heat_meter.assert_called_once()
    state = hass.states.get("sensor.heat_meter_heat_previous_year")
    assert state.state == STATE_UNAVAILABLE

    # Now 'enable' and see if next poll succeeds
    mock_heat_meter().read.side_effect = None
    mock_heat_meter.reset_mock()
    mock_heat_meter_response = MockHeatMeterResponse(
        heat_usage_gj=None,
        heat_usage_mwh=123.0,
        volume_usage_m3=456.0,
        heat_previous_year_gj=None,
        heat_previous_year_mwh=111.0,
        device_number="devicenr_789",
        meter_date_time=dt_util.as_utc(datetime.datetime(2022, 5, 19, 19, 41, 17)),
    )
    mock_heat_meter().read.return_value = mock_heat_meter_response
    async_fire_time_changed(hass, dt_util.utcnow() + POLLING_INTERVAL)
    await hass.async_block_till_done()
    mock_heat_meter.assert_called_once()
    state = hass.states.get("sensor.heat_meter_heat_previous_year")
    assert state.state == "111.0"
