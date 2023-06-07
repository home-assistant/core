"""Provide common Renault fixtures."""
from collections.abc import Generator
import contextlib
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from renault_api.kamereon import exceptions, schemas
from renault_api.renault_account import RenaultAccount

from homeassistant.components.renault.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import MOCK_ACCOUNT_ID, MOCK_CONFIG, MOCK_VEHICLES

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.renault.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="vehicle_type", params=MOCK_VEHICLES.keys())
def get_vehicle_type(request: pytest.FixtureRequest) -> str:
    """Parametrize vehicle type."""
    return request.param


@pytest.fixture(name="config_entry")
def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG,
        unique_id=MOCK_ACCOUNT_ID,
        options={},
        entry_id="123456",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="patch_renault_account")
async def patch_renault_account(hass: HomeAssistant) -> RenaultAccount:
    """Create a Renault account."""
    renault_account = RenaultAccount(
        MOCK_ACCOUNT_ID,
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        return_value=renault_account,
    ):
        yield renault_account


@pytest.fixture(name="patch_get_vehicles")
def patch_get_vehicles(vehicle_type: str):
    """Mock fixtures."""
    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        return_value=(
            schemas.KamereonVehiclesResponseSchema.loads(
                load_fixture(f"renault/vehicle_{vehicle_type}.json")
            )
        ),
    ):
        yield


def _get_fixtures(vehicle_type: str) -> MappingProxyType:
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
        "lock_status": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['lock_status']}")
            if "lock_status" in mock_vehicle["endpoints"]
            else load_fixture("renault/no_data.json")
        ).get_attributes(schemas.KamereonVehicleLockStatusDataSchema),
        "res_state": schemas.KamereonVehicleDataResponseSchema.loads(
            load_fixture(f"renault/{mock_vehicle['endpoints']['res_state']}")
            if "res_state" in mock_vehicle["endpoints"]
            else load_fixture("renault/no_data.json")
        ).get_attributes(schemas.KamereonVehicleResStateDataSchema),
    }


@pytest.fixture(name="fixtures_with_data")
def patch_fixtures_with_data(vehicle_type: str):
    """Mock fixtures."""
    mock_fixtures = _get_fixtures(vehicle_type)

    with patch(
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
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_lock_status",
        return_value=mock_fixtures["lock_status"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_res_state",
        return_value=mock_fixtures["res_state"],
    ):
        yield


@pytest.fixture(name="fixtures_with_no_data")
def patch_fixtures_with_no_data():
    """Mock fixtures."""
    mock_fixtures = _get_fixtures("")

    with patch(
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
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_lock_status",
        return_value=mock_fixtures["lock_status"],
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_res_state",
        return_value=mock_fixtures["res_state"],
    ):
        yield


@contextlib.contextmanager
def _patch_fixtures_with_side_effect(side_effect: Any):
    """Mock fixtures."""
    with patch(
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
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_lock_status",
        side_effect=side_effect,
    ), patch(
        "renault_api.renault_vehicle.RenaultVehicle.get_res_state",
        side_effect=side_effect,
    ):
        yield


@pytest.fixture(name="fixtures_with_access_denied_exception")
def patch_fixtures_with_access_denied_exception():
    """Mock fixtures."""
    access_denied_exception = exceptions.AccessDeniedException(
        "err.func.403",
        "Access is denied for this resource",
    )

    with _patch_fixtures_with_side_effect(access_denied_exception):
        yield


@pytest.fixture(name="fixtures_with_invalid_upstream_exception")
def patch_fixtures_with_invalid_upstream_exception():
    """Mock fixtures."""
    invalid_upstream_exception = exceptions.InvalidUpstreamException(
        "err.tech.500",
        "Invalid response from the upstream server (The request sent to the GDC is erroneous) ; 502 Bad Gateway",
    )

    with _patch_fixtures_with_side_effect(invalid_upstream_exception):
        yield


@pytest.fixture(name="fixtures_with_not_supported_exception")
def patch_fixtures_with_not_supported_exception():
    """Mock fixtures."""
    not_supported_exception = exceptions.NotSupportedException(
        "err.tech.501",
        "This feature is not technically supported by this gateway",
    )

    with _patch_fixtures_with_side_effect(not_supported_exception):
        yield
