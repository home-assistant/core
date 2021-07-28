"""Tests for the Renault integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from renault_api.kamereon import models, schemas
from renault_api.renault_vehicle import RenaultVehicle

from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    DOMAIN,
)
from homeassistant.components.renault.renault_vehicle import RenaultVehicleProxy
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import MOCK_VEHICLES

from tests.common import MockConfigEntry, load_fixture


async def setup_renault_integration(hass: HomeAssistant):
    """Create the Renault integration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source="user",
        data={
            CONF_LOCALE: "fr_FR",
            CONF_USERNAME: "email@test.com",
            CONF_PASSWORD: "test",
            CONF_KAMEREON_ACCOUNT_ID: "account_id_2",
        },
        unique_id="account_id_2",
        options={},
        entry_id="1",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.renault.RenaultHub.attempt_login", return_value=True
    ), patch("homeassistant.components.renault.RenaultHub.async_initialise"):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def get_fixtures(vehicle_type: str) -> dict[str, Any]:
    """Create a vehicle proxy for testing."""
    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    return {
        "battery_status": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['battery_status']}")
            if "battery_status" in mock_vehicle["endpoints"]
            else "{}"
        ).get_attributes(schemas.KamereonVehicleBatteryStatusDataSchema),
        "charge_mode": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['charge_mode']}")
            if "charge_mode" in mock_vehicle["endpoints"]
            else "{}"
        ).get_attributes(schemas.KamereonVehicleChargeModeDataSchema),
        "cockpit": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['cockpit']}")
            if "cockpit" in mock_vehicle["endpoints"]
            else "{}"
        ).get_attributes(schemas.KamereonVehicleCockpitDataSchema),
        "hvac_status": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['hvac_status']}")
            if "hvac_status" in mock_vehicle["endpoints"]
            else "{}"
        ).get_attributes(schemas.KamereonVehicleHvacStatusDataSchema),
    }


async def create_vehicle_proxy(
    hass: HomeAssistant, vehicle_type: str
) -> RenaultVehicleProxy:
    """Create a vehicle proxy for testing."""
    mock_vehicle = MOCK_VEHICLES[vehicle_type]
    mock_fixtures = get_fixtures(vehicle_type)

    vehicles_response: models.KamereonVehiclesResponse = (
        schemas.KamereonVehiclesResponseSchema.loads(
            load_fixture(f"renault/vehicle_{vehicle_type}.json")
        )
    )
    vehicle_details = vehicles_response.vehicleLinks[0].vehicleDetails
    vehicle = RenaultVehicle(
        vehicles_response.accountId,
        vehicle_details.vin,
        websession=aiohttp_client.async_get_clientsession(hass),
    )

    vehicle_proxy = RenaultVehicleProxy(
        hass, vehicle, vehicle_details, timedelta(seconds=300)
    )
    with patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.endpoint_available",
        side_effect=mock_vehicle["endpoints_available"],
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_battery_status",
        return_value=mock_fixtures["battery_status"],
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_charge_mode",
        return_value=mock_fixtures["charge_mode"],
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_cockpit",
        return_value=mock_fixtures["cockpit"],
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_hvac_status",
        return_value=mock_fixtures["hvac_status"],
    ):
        await vehicle_proxy.async_initialise()
    return vehicle_proxy


async def create_vehicle_proxy_with_side_effect(
    hass: HomeAssistant, vehicle_type: str, side_effect: Any
) -> RenaultVehicleProxy:
    """Create a vehicle proxy for testing unavailable entities."""
    mock_vehicle = MOCK_VEHICLES[vehicle_type]

    vehicles_response: models.KamereonVehiclesResponse = (
        schemas.KamereonVehiclesResponseSchema.loads(
            load_fixture(f"renault/vehicle_{vehicle_type}.json")
        )
    )
    vehicle_details = vehicles_response.vehicleLinks[0].vehicleDetails
    vehicle = RenaultVehicle(
        vehicles_response.accountId,
        vehicle_details.vin,
        websession=aiohttp_client.async_get_clientsession(hass),
    )

    vehicle_proxy = RenaultVehicleProxy(
        hass, vehicle, vehicle_details, timedelta(seconds=300)
    )
    with patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.endpoint_available",
        side_effect=mock_vehicle["endpoints_available"],
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_battery_status",
        side_effect=side_effect,
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_charge_mode",
        side_effect=side_effect,
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_cockpit",
        side_effect=side_effect,
    ), patch(
        "homeassistant.components.renault.renault_vehicle.RenaultVehicleProxy.get_hvac_status",
        side_effect=side_effect,
    ):
        await vehicle_proxy.async_initialise()
    return vehicle_proxy
