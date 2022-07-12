"""The tests for the Landis+Gyr Heat Meter sensor platform."""
from dataclasses import dataclass
import datetime
from unittest.mock import patch

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.landisgyr_heat_meter.const import DOMAIN
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@dataclass
class MockHeatMeterResponse:
    """Mock for HeatMeterResponse."""

    heat_usage_gj: dict
    volume_usage_m3: dict
    device_number: dict
    meter_date_time: dict


@patch("homeassistant.components.landisgyr_heat_meter.HeatMeterService")
async def test_create_sensors(mock_heat_meter, hass):
    """Test sensor."""
    entry_data = {
        "device": "/dev/USB0",
        "model": "LUGCUH50",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    mock_heat_meter_response = MockHeatMeterResponse(
        heat_usage_gj=123,
        volume_usage_m3=456,
        device_number="devicenr_789",
        meter_date_time=datetime.datetime(2022, 5, 19, 19, 41, 17),
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

    # check if 25 attributes have been created
    assert len(hass.states.async_all()) == 25
    entity_reg = entity_registry.async_get(hass)

    state = hass.states.get("sensor.heat_meter_heat_usage_gj")
    assert state
    assert state.state == "123"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "GJ"
    assert state.attributes.get("state_class") == SensorStateClass.TOTAL

    state = hass.states.get("sensor.heat_meter_volume_usage_m3")
    assert state
    assert state.state == "456"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == VOLUME_CUBIC_METERS
    assert state.attributes.get("state_class") == SensorStateClass.TOTAL

    state = hass.states.get("sensor.heat_meter_device_number")
    assert state
    assert state.state == "devicenr_789"
    assert state.attributes.get("state_class") is None
    entity_registry_entry = entity_reg.async_get("sensor.heat_meter_device_number")
    assert entity_registry_entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.heat_meter_meter_date_time")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get("state_class") is None
    entity_registry_entry = entity_reg.async_get("sensor.heat_meter_meter_date_time")
    assert entity_registry_entry.entity_category == EntityCategory.DIAGNOSTIC
