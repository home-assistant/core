"""Tests for the Renault integration."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from renault_api.kamereon import schemas
from renault_api.renault_account import RenaultAccount

from homeassistant.components.renault.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    ATTR_ICON,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceRegistry

from .const import ICON_FOR_EMPTY_VALUES, MOCK_CONFIG, MOCK_VEHICLES

from tests.common import MockConfigEntry, load_fixture


def get_mock_config_entry():
    """Create the Renault integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG,
        unique_id="account_id_1",
        options={},
        entry_id="123456",
    )


def get_fixtures(vehicle_type: str) -> dict[str, Any]:
    """Create a vehicle proxy for testing."""
    mock_vehicle = MOCK_VEHICLES.get(vehicle_type, {"endpoints": {}})
    return {
        "battery_status": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['battery_status']}")
            if "battery_status" in mock_vehicle["endpoints"]
            else load_fixture("renault/no_data.json")
        ).get_attributes(schemas.KamereonVehicleBatteryStatusDataSchema),
        "charge_mode": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['charge_mode']}")
            if "charge_mode" in mock_vehicle["endpoints"]
            else load_fixture("renault/no_data.json")
        ).get_attributes(schemas.KamereonVehicleChargeModeDataSchema),
        "cockpit": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['cockpit']}")
            if "cockpit" in mock_vehicle["endpoints"]
            else load_fixture("renault/no_data.json")
        ).get_attributes(schemas.KamereonVehicleCockpitDataSchema),
        "hvac_status": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['hvac_status']}")
            if "hvac_status" in mock_vehicle["endpoints"]
            else load_fixture("renault/no_data.json")
        ).get_attributes(schemas.KamereonVehicleHvacStatusDataSchema),
        "location": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['location']}")
            if "location" in mock_vehicle["endpoints"]
            else load_fixture("renault/no_data.json")
        ).get_attributes(schemas.KamereonVehicleLocationDataSchema),
    }


def get_no_data_icon(expected_entity: MappingProxyType):
    """Check attribute for  icon for inactive sensors."""
    entity_id = expected_entity["entity_id"]
    return ICON_FOR_EMPTY_VALUES.get(entity_id, expected_entity.get(ATTR_ICON))


async def setup_renault_integration_simple(hass: HomeAssistant):
    """Create the Renault integration."""
    config_entry = get_mock_config_entry()
    config_entry.add_to_hass(hass)

    renault_account = RenaultAccount(
        config_entry.unique_id,
        websession=aiohttp_client.async_get_clientsession(hass),
    )

    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        return_value=renault_account,
    ), patch("renault_api.renault_account.RenaultAccount.get_vehicles"):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def setup_renault_integration_vehicle(hass: HomeAssistant, vehicle_type: str):
    """Create the Renault integration."""
    config_entry = get_mock_config_entry()
    config_entry.add_to_hass(hass)

    renault_account = RenaultAccount(
        config_entry.unique_id,
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    mock_fixtures = get_fixtures(vehicle_type)

    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        return_value=renault_account,
    ), patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        return_value=(
            schemas.KamereonVehiclesResponseSchema.loads(
                load_fixture(f"renault/vehicle_{vehicle_type}.json")
            )
        ),
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.supports_endpoint",
        side_effect=mock_vehicle["endpoints_available"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.has_contract_for_endpoint",
        return_value=True,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_battery_status",
        return_value=mock_fixtures["battery_status"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_charge_mode",
        return_value=mock_fixtures["charge_mode"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_cockpit",
        return_value=mock_fixtures["cockpit"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_hvac_status",
        return_value=mock_fixtures["hvac_status"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_location",
        return_value=mock_fixtures["location"],
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def setup_renault_integration_vehicle_with_no_data(
    hass: HomeAssistant, vehicle_type: str
):
    """Create the Renault integration."""
    config_entry = get_mock_config_entry()
    config_entry.add_to_hass(hass)

    renault_account = RenaultAccount(
        config_entry.unique_id,
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    mock_fixtures = get_fixtures("")

    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        return_value=renault_account,
    ), patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        return_value=(
            schemas.KamereonVehiclesResponseSchema.loads(
                load_fixture(f"renault/vehicle_{vehicle_type}.json")
            )
        ),
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.supports_endpoint",
        side_effect=mock_vehicle["endpoints_available"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.has_contract_for_endpoint",
        return_value=True,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_battery_status",
        return_value=mock_fixtures["battery_status"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_charge_mode",
        return_value=mock_fixtures["charge_mode"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_cockpit",
        return_value=mock_fixtures["cockpit"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_hvac_status",
        return_value=mock_fixtures["hvac_status"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_location",
        return_value=mock_fixtures["location"],
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def setup_renault_integration_vehicle_with_side_effect(
    hass: HomeAssistant, vehicle_type: str, side_effect: Any
):
    """Create the Renault integration."""
    config_entry = get_mock_config_entry()
    config_entry.add_to_hass(hass)

    renault_account = RenaultAccount(
        config_entry.unique_id,
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    mock_vehicle = MOCK_VEHICLES[vehicle_type]

    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        return_value=renault_account,
    ), patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        return_value=(
            schemas.KamereonVehiclesResponseSchema.loads(
                load_fixture(f"renault/vehicle_{vehicle_type}.json")
            )
        ),
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.supports_endpoint",
        side_effect=mock_vehicle["endpoints_available"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.has_contract_for_endpoint",
        return_value=True,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_battery_status",
        side_effect=side_effect,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_charge_mode",
        side_effect=side_effect,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_cockpit",
        side_effect=side_effect,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_hvac_status",
        side_effect=side_effect,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_location",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def check_device_registry(
    device_registry: DeviceRegistry, expected_device: dict[str, Any]
) -> None:
    """Ensure that the expected_device is correctly registered."""
    assert len(device_registry.devices) == 1
    registry_entry = device_registry.async_get_device(expected_device[ATTR_IDENTIFIERS])
    assert registry_entry is not None
    assert registry_entry.identifiers == expected_device[ATTR_IDENTIFIERS]
    assert registry_entry.manufacturer == expected_device[ATTR_MANUFACTURER]
    assert registry_entry.name == expected_device[ATTR_NAME]
    assert registry_entry.model == expected_device[ATTR_MODEL]
    assert registry_entry.sw_version == expected_device[ATTR_SW_VERSION]
