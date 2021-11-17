"""Tests for Renault sensors."""
from unittest.mock import patch

import pytest
from renault_api.kamereon import schemas

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import check_device_registry, check_entities_no_data
from .const import ATTR_ENTITY_ID, MOCK_VEHICLES

from tests.common import load_fixture, mock_device_registry, mock_registry

pytestmark = pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")


@pytest.fixture(autouse=True)
def override_platforms():
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", [BUTTON_DOMAIN]):
        yield


@pytest.mark.usefixtures("fixtures_with_data")
async def test_buttons(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[BUTTON_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)

    check_entities_no_data(hass, entity_registry, expected_entities, STATE_UNKNOWN)


@pytest.mark.usefixtures("fixtures_with_no_data")
async def test_button_empty(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with empty data from Renault."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[BUTTON_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)
    check_entities_no_data(hass, entity_registry, expected_entities, STATE_UNKNOWN)


@pytest.mark.usefixtures("fixtures_with_invalid_upstream_exception")
async def test_button_errors(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with temporary failure."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[BUTTON_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)

    check_entities_no_data(hass, entity_registry, expected_entities, STATE_UNKNOWN)


@pytest.mark.usefixtures("fixtures_with_access_denied_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_button_access_denied(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with access denied failure."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[BUTTON_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)

    check_entities_no_data(hass, entity_registry, expected_entities, STATE_UNKNOWN)


@pytest.mark.usefixtures("fixtures_with_not_supported_exception")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_button_not_supported(
    hass: HomeAssistant, config_entry: ConfigEntry, vehicle_type: str
):
    """Test for Renault device trackers with not supported failure."""

    entity_registry = mock_registry(hass)
    device_registry = mock_device_registry(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    check_device_registry(device_registry, mock_vehicle["expected_device"])

    expected_entities = mock_vehicle[BUTTON_DOMAIN]
    assert len(entity_registry.entities) == len(expected_entities)

    check_entities_no_data(hass, entity_registry, expected_entities, STATE_UNKNOWN)


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_button_start_charge(hass: HomeAssistant, config_entry: ConfigEntry):
    """Test that button invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data = {
        ATTR_ENTITY_ID: "button.reg_number_start_charge",
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_charge_start",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_charge_start.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == ()


@pytest.mark.usefixtures("fixtures_with_data")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_button_start_air_conditioner(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    """Test that button invokes renault_api with correct data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data = {
        ATTR_ENTITY_ID: "button.reg_number_start_air_conditioner",
    }

    with patch(
        "renault_api.renault_vehicle.RenaultVehicle.set_ac_start",
        return_value=(
            schemas.KamereonVehicleHvacStartActionDataSchema.loads(
                load_fixture("renault/action.set_ac_start.json")
            )
        ),
    ) as mock_action:
        await hass.services.async_call(
            BUTTON_DOMAIN, SERVICE_PRESS, service_data=data, blocking=True
        )
    assert len(mock_action.mock_calls) == 1
    assert mock_action.mock_calls[0][1] == (21, None)
