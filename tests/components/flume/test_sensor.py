"""Test the flume sensor."""

from unittest.mock import patch

import pytest
from requests_mock.mocker import Mocker

from homeassistant.components.flume.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform, UnitOfVolume, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .conftest import DEVICE_LIST, DEVICE_LIST_URL

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def platforms_fixture():
    """Return the platforms to be loaded for this test."""
    with patch("homeassistant.components.flume.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("access_token")
async def test_sensors(
    hass: HomeAssistant,
    requests_mock: Mocker,
    config_entry: MockConfigEntry,
) -> None:
    """Test sensors."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    # Add TZ to the device list from conftest
    devices = [dict(device) for device in DEVICE_LIST]
    for device in devices:
        if "location" in device:
            device["location"] = dict(device["location"])
            device["location"]["tz"] = "America/New_York"

    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        status_code=200,
        json={
            "data": devices,
        },
    )

    # Mock the data returned by PyFlume
    flume_values = {
        "current_interval": 1.23,
        "month_to_date": 100.1,
        "week_to_date": 50.5,
        "today": 10.2,
        "last_60_min": 5.5,
        "last_24_hrs": 20.4,
        "last_30_days": 150.8,
    }

    with patch("homeassistant.components.flume.sensor.FlumeData") as mock_flume_data:
        instance = mock_flume_data.return_value
        instance.values = flume_values
        instance.update_force.return_value = None
        instance.query_payload = {}

        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)

    # current_interval
    entry = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "current_interval_1234"
    )
    state = hass.states.get(entry)
    assert state.state == "1.23"
    assert (
        state.attributes["unit_of_measurement"]
        == UnitOfVolumeFlowRate.GALLONS_PER_MINUTE
    )
    assert state.attributes["device_class"] == SensorDeviceClass.VOLUME_FLOW_RATE

    # month_to_date
    entry = entity_registry.async_get_entity_id("sensor", DOMAIN, "month_to_date_1234")
    state = hass.states.get(entry)
    assert state.state == "100.1"
    assert state.attributes["unit_of_measurement"] == UnitOfVolume.GALLONS
    assert state.attributes["device_class"] == SensorDeviceClass.WATER

    # week_to_date
    entry = entity_registry.async_get_entity_id("sensor", DOMAIN, "week_to_date_1234")
    state = hass.states.get(entry)
    assert state.state == "50.5"
    assert state.attributes["unit_of_measurement"] == UnitOfVolume.GALLONS
    assert state.attributes["device_class"] == SensorDeviceClass.WATER

    # today
    entry = entity_registry.async_get_entity_id("sensor", DOMAIN, "today_1234")
    state = hass.states.get(entry)
    assert state.state == "10.2"
    assert state.attributes["unit_of_measurement"] == UnitOfVolume.GALLONS
    assert state.attributes["device_class"] == SensorDeviceClass.WATER

    # last_60_min
    entry = entity_registry.async_get_entity_id("sensor", DOMAIN, "last_60_min_1234")
    state = hass.states.get(entry)
    assert state.state == "5.5"
    assert (
        state.attributes["unit_of_measurement"] == UnitOfVolumeFlowRate.GALLONS_PER_HOUR
    )
    assert state.attributes["device_class"] == SensorDeviceClass.VOLUME_FLOW_RATE

    # last_24_hrs
    entry = entity_registry.async_get_entity_id("sensor", DOMAIN, "last_24_hrs_1234")
    state = hass.states.get(entry)
    assert state.state == "20.4"
    assert (
        state.attributes["unit_of_measurement"] == UnitOfVolumeFlowRate.GALLONS_PER_DAY
    )
    assert state.attributes["device_class"] == SensorDeviceClass.VOLUME_FLOW_RATE

    # last_30_days
    entry = entity_registry.async_get_entity_id("sensor", DOMAIN, "last_30_days_1234")
    state = hass.states.get(entry)
    assert state.state == "150.8"
    assert state.attributes["unit_of_measurement"] == "gal/mo"
    assert "device_class" not in state.attributes
