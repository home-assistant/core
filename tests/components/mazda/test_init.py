"""Tests for the Mazda Connected Services integration."""
from datetime import timedelta
import json
from unittest.mock import patch

from pymazda import MazdaAuthenticationException, MazdaException
import pytest
import voluptuous as vol

from homeassistant.components.mazda.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture

FIXTURE_USER_INPUT = {
    CONF_EMAIL: "example@example.com",
    CONF_PASSWORD: "password",
    CONF_REGION: "MNAO",
}


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test the Mazda configuration entry not ready."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        side_effect=MazdaException("Unknown error"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_auth_failure(hass: HomeAssistant):
    """Test auth failure during setup."""
    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        side_effect=MazdaAuthenticationException("Login failed"),
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "user"


async def test_update_auth_failure(hass: HomeAssistant):
    """Test auth failure during data update."""
    get_vehicles_fixture = json.loads(load_fixture("mazda/get_vehicles.json"))
    get_vehicle_status_fixture = json.loads(
        load_fixture("mazda/get_vehicle_status.json")
    )

    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        return_value=True,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        return_value=get_vehicles_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicle_status",
        return_value=get_vehicle_status_fixture,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        side_effect=MazdaAuthenticationException("Login failed"),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "user"


async def test_update_general_failure(hass: HomeAssistant):
    """Test general failure during data update."""
    get_vehicles_fixture = json.loads(load_fixture("mazda/get_vehicles.json"))
    get_vehicle_status_fixture = json.loads(
        load_fixture("mazda/get_vehicle_status.json")
    )

    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        return_value=True,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        return_value=get_vehicles_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicle_status",
        return_value=get_vehicle_status_fixture,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        side_effect=Exception("Unknown exception"),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
        await hass.async_block_till_done()

    entity = hass.states.get("sensor.my_mazda3_fuel_remaining_percentage")
    assert entity is not None
    assert entity.state == STATE_UNAVAILABLE


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test the Mazda configuration entry unloading."""
    await init_integration(hass)
    assert hass.data[DOMAIN]

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()
    assert entries[0].state is ConfigEntryState.NOT_LOADED


async def test_init_electric_vehicle(hass):
    """Test initialization of the integration with an electric vehicle."""
    client_mock = await init_integration(hass, electric_vehicle=True)

    client_mock.get_vehicles.assert_called_once()
    client_mock.get_vehicle_status.assert_called_once()
    client_mock.get_ev_vehicle_status.assert_called_once()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


async def test_device_nickname(hass):
    """Test creation of the device when vehicle has a nickname."""
    await init_integration(hass, use_nickname=True)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )

    assert reg_device.model == "2021 MAZDA3 2.5 S SE AWD"
    assert reg_device.manufacturer == "Mazda"
    assert reg_device.name == "My Mazda3"


async def test_device_no_nickname(hass):
    """Test creation of the device when vehicle has no nickname."""
    await init_integration(hass, use_nickname=False)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )

    assert reg_device.model == "2021 MAZDA3 2.5 S SE AWD"
    assert reg_device.manufacturer == "Mazda"
    assert reg_device.name == "2021 MAZDA3 2.5 S SE AWD"


@pytest.mark.parametrize(
    "service, service_data, expected_args",
    [
        (
            "send_poi",
            {"latitude": 1.2345, "longitude": 2.3456, "poi_name": "Work"},
            [12345, 1.2345, 2.3456, "Work"],
        ),
    ],
)
async def test_services(hass, service, service_data, expected_args):
    """Test service calls."""
    client_mock = await init_integration(hass)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )
    device_id = reg_device.id

    service_data["device_id"] = device_id

    await hass.services.async_call(DOMAIN, service, service_data, blocking=True)
    await hass.async_block_till_done()

    api_method = getattr(client_mock, service)
    api_method.assert_called_once_with(*expected_args)


async def test_service_invalid_device_id(hass):
    """Test service call when the specified device ID is invalid."""
    await init_integration(hass)

    with pytest.raises(vol.error.MultipleInvalid) as err:
        await hass.services.async_call(
            DOMAIN,
            "send_poi",
            {
                "device_id": "invalid",
                "latitude": 1.2345,
                "longitude": 6.7890,
                "poi_name": "poi_name",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    assert "Invalid device ID" in str(err.value)


async def test_service_device_id_not_mazda_vehicle(hass):
    """Test service call when the specified device ID is not the device ID of a Mazda vehicle."""
    await init_integration(hass)

    device_registry = dr.async_get(hass)
    # Create another device and pass its device ID.
    # Service should fail because device is from wrong domain.
    other_device = device_registry.async_get_or_create(
        config_entry_id="test_config_entry_id",
        identifiers={("OTHER_INTEGRATION", "ID_FROM_OTHER_INTEGRATION")},
    )

    with pytest.raises(vol.error.MultipleInvalid) as err:
        await hass.services.async_call(
            DOMAIN,
            "send_poi",
            {
                "device_id": other_device.id,
                "latitude": 1.2345,
                "longitude": 6.7890,
                "poi_name": "poi_name",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    assert "Device ID is not a Mazda vehicle" in str(err.value)


async def test_service_vehicle_id_not_found(hass):
    """Test service call when the vehicle ID is not found."""
    await init_integration(hass)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )
    device_id = reg_device.id

    entries = hass.config_entries.async_entries(DOMAIN)
    entry_id = entries[0].entry_id

    # Remove vehicle info from hass.data so that vehicle ID will not be found
    hass.data[DOMAIN][entry_id]["vehicles"] = []

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "send_poi",
            {
                "device_id": device_id,
                "latitude": 1.2345,
                "longitude": 6.7890,
                "poi_name": "poi_name",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    assert str(err.value) == "Vehicle ID not found"


async def test_service_mazda_api_error(hass):
    """Test the Mazda API raising an error when a service is called."""
    get_vehicles_fixture = json.loads(load_fixture("mazda/get_vehicles.json"))
    get_vehicle_status_fixture = json.loads(
        load_fixture("mazda/get_vehicle_status.json")
    )

    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        return_value=True,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        return_value=get_vehicles_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicle_status",
        return_value=get_vehicle_status_fixture,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )
    device_id = reg_device.id

    with patch(
        "homeassistant.components.mazda.MazdaAPI.send_poi",
        side_effect=MazdaException("Test error"),
    ), pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "send_poi",
            {
                "device_id": device_id,
                "latitude": 1.2345,
                "longitude": 6.7890,
                "poi_name": "poi_name",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

    assert str(err.value) == "Test error"
