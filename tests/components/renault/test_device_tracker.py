"""Tests for Renault sensors."""
from unittest.mock import patch

import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import check_device_registry, get_no_data_icon
from .const import DYNAMIC_ATTRIBUTES, FIXED_ATTRIBUTES, MOCK_VEHICLES

from tests.common import mock_device_registry, mock_registry

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [DEVICE_TRACKER_DOMAIN]):
        yield


@pytest.mark.usefixtures("fixtures_with_data")
async def test_device_trackers(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[DEVICE_TRACKER_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)
    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity["unique_id"]
        state = hass.states.get(entity_id)
        assert state.state == expected_entity["result"]
        for attr in FIXED_ATTRIBUTES + DYNAMIC_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)


@pytest.mark.usefixtures("fixtures_with_no_data")
async def test_device_tracker_empty(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with empty data from Renault."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[DEVICE_TRACKER_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)
    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity["unique_id"]
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNKNOWN
        for attr in FIXED_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)
        # Check dynamic attributes:
        assert state.attributes.get(ATTR_ICON) == get_no_data_icon(expected_entity)


@pytest.mark.usefixtures("fixtures_with_invalid_upstream_exception")
async def test_device_tracker_errors(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with temporary failure."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[DEVICE_TRACKER_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)
    for expected_entity in expected_entities:
        entity_id = expected_entity["entity_id"]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity["unique_id"]
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE
        for attr in FIXED_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)
        # Check dynamic attributes:
        assert state.attributes.get(ATTR_ICON) == get_no_data_icon(expected_entity)


@pytest.mark.usefixtures("fixtures_with_access_denied_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_device_tracker_access_denied(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with access denied failure."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_not_supported_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_device_tracker_not_supported(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with not supported failure."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0
