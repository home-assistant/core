"""Tests for the srp_energy sensor platform."""
from datetime import timedelta
import logging

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.srp_energy import (
    ATTRIBUTION,
    DEVICE_NAME_ENERGY,
    DEVICE_NAME_PRICE,
    DOMAIN,
    TIME_DELTA_BETWEEN_UPDATES,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CURRENCY_DOLLAR, ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import TEST_DATE, TEST_SENSOR_COUNT

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)

GUID_LENGTH = 32


async def test_loading_sensors(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the srp energy sensors."""
    # Validate the Config Entry was initialized
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    # Check sensors were loaded
    assert len(hass.states.async_all()) == TEST_SENSOR_COUNT


async def test_total_energy_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the total energy sensor."""
    # Test Total Energy Entity
    sensor_entity_id = "sensor.test_home_energy_consumption_this_month"

    # Validate the Config Entry was initialized
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    # Check Device Registry
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{init_integration.title}_{DEVICE_NAME_ENERGY}")}
    )
    assert device_entry is not None
    assert len(device_entry.id) == GUID_LENGTH
    assert device_entry.entry_type == dr.DeviceEntryType.SERVICE
    assert device_entry.manufacturer == "srpnet.com"
    assert device_entry.model == "Service Api"
    assert device_entry.name == "Test Home Energy consumption"
    assert device_entry.configuration_url == "https://www.srpnet.com/"
    assert device_entry.connections == set()
    assert (
        DOMAIN,
        f"{init_integration.title}_{DEVICE_NAME_ENERGY}",
    ) in device_entry.identifiers

    # Check Entity Registry
    entity_registry = er.async_get(hass)
    er_entries = er.async_entries_for_device(entity_registry, device_entry.id)
    assert er_entries is not None
    assert len(er_entries) > 0
    entity_entry = er_entries[0]
    assert entity_entry.entity_id == sensor_entity_id
    assert entity_entry.unique_id == "123456789_energy_usage_this_month"
    assert entity_entry.original_name == "This month"
    assert entity_entry.device_class is None
    assert len(entity_entry.device_id or "") == GUID_LENGTH
    assert len(entity_entry.id) == GUID_LENGTH
    assert entity_entry.name is None

    # Check Sensor Entity State
    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None
    assert sensor.entity_id == sensor_entity_id
    assert sensor.name == "Test Home Energy consumption This month"
    assert sensor.state == "69.4"
    assert sensor.attributes["device_class"] == SensorDeviceClass.ENERGY
    assert sensor.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING
    assert sensor.attributes["unit_of_measurement"] == ENERGY_KILO_WATT_HOUR
    assert sensor.attributes["attribution"] == ATTRIBUTION
    assert (
        sensor.attributes["friendly_name"] == "Test Home Energy consumption This month"
    )


async def test_total_energy_price_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the total energy price sensor."""
    sensor_entity_id = "sensor.test_home_energy_consumption_price_this_month"

    # Validate the Config Entry was initialized
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    # Check Device Registry
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{init_integration.title}_{DEVICE_NAME_PRICE}")}
    )
    assert device_entry is not None
    assert len(device_entry.id) == GUID_LENGTH
    assert device_entry.entry_type == dr.DeviceEntryType.SERVICE
    assert device_entry.manufacturer == "srpnet.com"
    assert device_entry.model == "Service Api"
    assert device_entry.name == "Test Home Energy consumption price"
    assert device_entry.configuration_url == "https://www.srpnet.com/"
    assert device_entry.connections == set()
    assert (
        DOMAIN,
        f"{init_integration.title}_{DEVICE_NAME_PRICE}",
    ) in device_entry.identifiers

    # Check Entity Registry
    entity_registry = er.async_get(hass)
    er_entries = er.async_entries_for_device(entity_registry, device_entry.id)

    assert er_entries is not None
    assert len(er_entries) > 0
    entity_entry = er_entries[0]
    assert len(entity_entry.config_entry_id or "") == GUID_LENGTH
    assert entity_entry.entity_id == sensor_entity_id
    assert entity_entry.unique_id == "123456789_energy_usage_price_this_month"
    assert entity_entry.original_name == "This month"
    assert entity_entry.device_class is None
    assert len(entity_entry.device_id or "") == GUID_LENGTH
    assert len(entity_entry.id) == GUID_LENGTH
    assert entity_entry.name is None

    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None
    assert sensor.attributes["device_class"] == SensorDeviceClass.MONETARY
    assert sensor.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING
    assert sensor.attributes["unit_of_measurement"] == CURRENCY_DOLLAR
    assert sensor.attributes["attribution"] == ATTRIBUTION
    assert (
        sensor.attributes["friendly_name"]
        == "Test Home Energy consumption price This month"
    )
    assert sensor.state == "10.02"


async def test_fetching_new_data(
    hass: HomeAssistant, init_integration: MockConfigEntry, freezer
) -> None:
    """Test the total energy price sensor."""
    _LOGGER.debug("Starting Test")
    assert init_integration.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    sensor_entity_id = "sensor.test_home_energy_consumption_price_this_month"

    _LOGGER.debug("Getting sensor state")
    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None
    assert sensor.state == "10.02"

    # Test fetching new data
    future = TEST_DATE + (2 * TIME_DELTA_BETWEEN_UPDATES)
    _LOGGER.debug("Changing to future time %s", future)
    freezer.move_to(future)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    _LOGGER.debug("Checking sensor state again")
    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None
    assert sensor.state == "10.31"


async def test_data_update_invalid_dates(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry,
    mock_srp_energy,
) -> None:
    """Test the sensors data update with bad dates."""
    # Need to mock side effect on mock_srp_energy.
    # Can't use init_integration
    sensor_entity_id = "sensor.test_home_energy_consumption_this_month"

    freezer.move_to(TEST_DATE)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    assert len(hass.states.async_all()) == TEST_SENSOR_COUNT

    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None

    mock_srp_energy.usage.side_effect = ValueError

    # Test fetching new data
    future = TEST_DATE + timedelta(hours=9)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None
    assert sensor.state == "69.4"


async def test_data_update_api_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry,
    mock_srp_energy,
) -> None:
    """Test the srp energy sensors with api failure."""
    # Need to mock side effect on mock_srp_energy.
    # Can't use init_integration
    sensor_entity_id = "sensor.test_home_energy_consumption_this_month"

    freezer.move_to(TEST_DATE)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN]

    assert len(hass.states.async_all()) == TEST_SENSOR_COUNT

    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None

    mock_srp_energy.usage.side_effect = Exception

    # Test fetching new data
    future = TEST_DATE + timedelta(hours=9)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    sensor = hass.states.get(sensor_entity_id)
    assert sensor is not None
    assert sensor.state == "69.4"
