"""The tests for the Landis+Gyr Heat Meter sensor platform."""
from dataclasses import dataclass
import datetime
from unittest.mock import patch

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.landisgyr_heat_meter.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, mock_restore_cache_with_extra_data


@dataclass
class MockHeatMeterResponse:
    """Mock for HeatMeterResponse."""

    heat_usage_gj: int
    volume_usage_m3: int
    heat_previous_year_gj: int
    device_number: str
    meter_date_time: datetime.datetime


@patch("homeassistant.components.landisgyr_heat_meter.ultraheat_api.HeatMeterService")
async def test_create_sensors(
    mock_heat_meter, hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    mock_heat_meter_response = MockHeatMeterResponse(
        heat_usage_gj=123,
        volume_usage_m3=456,
        heat_previous_year_gj=111,
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

    # check if 26 attributes have been created
    assert len(hass.states.async_all()) == 27

    state = hass.states.get("sensor.heat_meter_heat_usage")
    assert state
    assert state.state == "34.16669"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.MEGA_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY

    state = hass.states.get("sensor.heat_meter_volume_usage")
    assert state
    assert state.state == "456"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.CUBIC_METERS
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL

    state = hass.states.get("sensor.heat_meter_device_number")
    assert state
    assert state.state == "devicenr_789"
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    entity_registry_entry = entity_registry.async_get("sensor.heat_meter_device_number")
    assert entity_registry_entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.heat_meter_meter_date_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    entity_registry_entry = entity_registry.async_get(
        "sensor.heat_meter_meter_date_time"
    )
    assert entity_registry_entry.entity_category == EntityCategory.DIAGNOSTIC


@patch("homeassistant.components.landisgyr_heat_meter.ultraheat_api.HeatMeterService")
async def test_restore_state(mock_heat_meter, hass: HomeAssistant) -> None:
    """Test sensor restore state."""
    # Home assistant is not running yet
    hass.state = CoreState.not_running
    last_reset = "2022-07-01T00:00:00.000000+00:00"
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.heat_meter_heat_usage",
                    "34167",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.MEGA_WATT_HOUR,
                        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
                    },
                ),
                {
                    "native_value": 34167,
                    "native_unit_of_measurement": UnitOfEnergy.MEGA_WATT_HOUR,
                    "icon": "mdi:fire",
                    "last_reset": last_reset,
                },
            ),
            (
                State(
                    "sensor.heat_meter_volume_usage",
                    "456",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.CUBIC_METERS,
                        ATTR_STATE_CLASS: SensorStateClass.TOTAL,
                    },
                ),
                {
                    "native_value": 456,
                    "native_unit_of_measurement": UnitOfVolume.CUBIC_METERS,
                    "icon": "mdi:fire",
                    "last_reset": last_reset,
                },
            ),
            (
                State(
                    "sensor.heat_meter_device_number",
                    "devicenr_789",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {
                    "native_value": "devicenr_789",
                    "native_unit_of_measurement": None,
                    "last_reset": last_reset,
                },
            ),
        ],
    )
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
        "device_number": "123456789",
    }

    # create and add entry
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # restore from cache
    state = hass.states.get("sensor.heat_meter_heat_usage")
    assert state
    assert state.state == "34167"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.MEGA_WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL

    state = hass.states.get("sensor.heat_meter_volume_usage")
    assert state
    assert state.state == "456"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.CUBIC_METERS
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL

    state = hass.states.get("sensor.heat_meter_device_number")
    assert state
    assert state.state == "devicenr_789"
    assert state.attributes.get(ATTR_STATE_CLASS) is None
