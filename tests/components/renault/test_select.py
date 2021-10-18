"""Tests for Renault selects."""
from unittest.mock import patch

import pytest
from renault_api.kamereon import schemas

from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.components.select.const import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import check_device_registry, get_no_data_icon
from .const import DYNAMIC_ATTRIBUTES, FIXED_ATTRIBUTES, MOCK_VEHICLES

from tests.common import load_fixture, mock_device_registry, mock_registry

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [SELECT_DOMAIN]):
        yield


@pytest.mark.usefixtures("fixtures_with_data")
async def test_selects(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault selects."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[SELECT_DOMAIN]
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
async def test_select_empty(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault selects with empty data from Renault."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[SELECT_DOMAIN]
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
async def test_select_errors(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault selects with temporary failure."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[SELECT_DOMAIN]
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
async def test_select_access_denied(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault selects with access denied failure."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_not_supported_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_select_not_supported(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault selects with access denied failure."""
    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    assert len(entity_registry.entities) == 0


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_select_charge_mode(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test that service invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data = {
        ATTR_ENTITY_ID: "select.charge_mode",
        ATTR_OPTION: "always",
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_charge_mode",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_charge_mode.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            SELECT_DOMAIN, SERVICE_SELECT_OPTION, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ("always",)
