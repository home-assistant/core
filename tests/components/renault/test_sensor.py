"""Tests for Renault sensors."""
from copy import deepcopy
from types import MappingProxyType
from unittest.mock import patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    LENGTH_MILES,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntryDisabler

from . import (
    check_device_registry,
    check_entities,
    check_entities_no_data,
    check_entities_unavailable,
)
from .const import ATTR_DEFAULT_DISABLED, MOCK_VEHICLES

from tests.common import mock_device_registry, mock_registry

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [Platform.SENSOR]):
        yield


def _check_and_enable_disabled_entities(
    entity_registry: EntityRegistry, expected_entities: MappingProxyType
) -> None:
    """Ensure that the expected_entities are correctly disabled."""
    for expected_entity in expected_entities:
        if expected_entity.get(ATTR_DEFAULT_DISABLED):
            entity_id = expected_entity[ATTR_ENTITY_ID]
            registry_entry = entity_registry.entities.get(entity_id)
            assert registry_entry.disabled
            assert registry_entry.disabled_by is RegistryEntryDisabler.INTEGRATION
            entity_registry.async_update_entity(entity_id, **{"disabled_by": None})


@pytest.mark.usefixtures("fixtures_with_data")
async def test_sensors(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault sensors."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[Platform.SENSOR]
    assert len(entity_registry.entities) == len(expected_entities)

    _check_and_enable_disabled_entities(entity_registry, expected_entities)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_miles_sensor(
    hass: HomeAssistant, miles_config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault sensors."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(miles_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = deepcopy(mock_vehicle[Platform.SENSOR])
    # sensor.reg_number_battery_autonomy
    expected_entities[0][ATTR_STATE] = "88"
    expected_entities[0][ATTR_UNIT_OF_MEASUREMENT] = LENGTH_MILES
    # sensor.reg_number_mileage
    expected_entities[8][ATTR_STATE] = "30518"
    expected_entities[8][ATTR_UNIT_OF_MEASUREMENT] = LENGTH_MILES
    assert len(entity_registry.entities) == len(expected_entities)

    _check_and_enable_disabled_entities(entity_registry, expected_entities)
    await hass.config_entries.async_reload(miles_config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("fixtures_with_no_data")
async def test_sensor_empty(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault sensors with empty data from Renault."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[Platform.SENSOR]
    assert len(entity_registry.entities) == len(expected_entities)

    _check_and_enable_disabled_entities(entity_registry, expected_entities)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities_no_data(hass, entity_registry, expected_entities, STATE_UNKNOWN)


@pytest.mark.usefixtures("fixtures_with_invalid_upstream_exception")
async def test_sensor_errors(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault sensors with temporary failure."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[Platform.SENSOR]
    assert len(entity_registry.entities) == len(expected_entities)

    _check_and_enable_disabled_entities(entity_registry, expected_entities)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    check_entities_unavailable(hass, entity_registry, expected_entities)


@pytest.mark.usefixtures("fixtures_with_access_denied_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_access_denied(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault sensors with access denied failure."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_not_supported_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_sensor_not_supported(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault sensors with access denied failure."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0
