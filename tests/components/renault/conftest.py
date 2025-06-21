"""Provide common Renault fixtures."""

from collections.abc import AsyncGenerator, Generator
import contextlib
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest
from renault_api.kamereon import exceptions, models, schemas
from renault_api.renault_account import RenaultAccount

from homeassistant.components.renault.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import MOCK_ACCOUNT_ID, MOCK_CONFIG, MOCK_VEHICLES

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
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
async def patch_renault_account(hass: HomeAssistant) -> AsyncGenerator[RenaultAccount]:
    """Create a Renault account."""
    renault_account = RenaultAccount(
        MOCK_ACCOUNT_ID,
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    with (
        patch("renault_api.renault_session.RenaultSession.login"),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_account",
            return_value=renault_account,
        ),
    ):
        yield renault_account


@pytest.fixture(name="patch_get_vehicles")
def patch_get_vehicles(vehicle_type: str) -> Generator[None]:
    """Mock fixtures."""
    fixture_code = vehicle_type if vehicle_type in MOCK_VEHICLES else "zoe_40"
    return_value: models.KamereonVehiclesResponse = (
        schemas.KamereonVehiclesResponseSchema.loads(
            load_fixture(f"renault/vehicle_{fixture_code}.json")
        )
    )

    if vehicle_type == "missing_details":
        return_value.vehicleLinks[0].vehicleDetails = None
    elif vehicle_type == "multi":
        return_value.vehicleLinks.extend(
            schemas.KamereonVehiclesResponseSchema.loads(
                load_fixture("renault/vehicle_captur_fuel.json")
            ).vehicleLinks
        )

    with patch(
        "renault_api.renault_account.RenaultAccount.get_vehicles",
        return_value=return_value,
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


@contextlib.contextmanager
def patch_get_vehicle_data() -> Generator[dict[str, AsyncMock]]:
    """Mock get_vehicle_data methods."""
    with (
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_battery_status"
        ) as get_battery_status,
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_charge_mode"
        ) as get_charge_mode,
        patch("renault_api.renault_vehicle.RenaultVehicle.get_cockpit") as get_cockpit,
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_hvac_status"
        ) as get_hvac_status,
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_location"
        ) as get_location,
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_lock_status"
        ) as get_lock_status,
        patch(
            "renault_api.renault_vehicle.RenaultVehicle.get_res_state"
        ) as get_res_state,
    ):
        yield {
            "battery_status": get_battery_status,
            "charge_mode": get_charge_mode,
            "cockpit": get_cockpit,
            "hvac_status": get_hvac_status,
            "location": get_location,
            "lock_status": get_lock_status,
            "res_state": get_res_state,
        }


@pytest.fixture(name="fixtures_with_data")
def patch_fixtures_with_data(vehicle_type: str) -> Generator[dict[str, AsyncMock]]:
    """Mock fixtures."""
    mock_fixtures = _get_fixtures(vehicle_type)

    with patch_get_vehicle_data() as patches:
        for key, value in patches.items():
            value.return_value = mock_fixtures[key]
        yield patches


@pytest.fixture(name="fixtures_with_no_data")
def patch_fixtures_with_no_data() -> Generator[dict[str, AsyncMock]]:
    """Mock fixtures."""
    mock_fixtures = _get_fixtures("")

    with patch_get_vehicle_data() as patches:
        for key, value in patches.items():
            value.return_value = mock_fixtures[key]
        yield patches


@pytest.fixture(name="fixtures_with_access_denied_exception")
def patch_fixtures_with_access_denied_exception() -> Generator[dict[str, AsyncMock]]:
    """Mock fixtures."""
    access_denied_exception = exceptions.AccessDeniedException(
        "err.func.403",
        "Access is denied for this resource",
    )

    with patch_get_vehicle_data() as patches:
        for value in patches.values():
            value.side_effect = access_denied_exception
        yield patches


@pytest.fixture(name="fixtures_with_invalid_upstream_exception")
def patch_fixtures_with_invalid_upstream_exception() -> Generator[dict[str, AsyncMock]]:
    """Mock fixtures."""
    invalid_upstream_exception = exceptions.InvalidUpstreamException(
        "err.tech.500",
        "Invalid response from the upstream server (The request sent to the GDC is erroneous) ; 502 Bad Gateway",
    )

    with patch_get_vehicle_data() as patches:
        for value in patches.values():
            value.side_effect = invalid_upstream_exception
        yield patches


@pytest.fixture(name="fixtures_with_not_supported_exception")
def patch_fixtures_with_not_supported_exception() -> Generator[dict[str, AsyncMock]]:
    """Mock fixtures."""
    not_supported_exception = exceptions.NotSupportedException(
        "err.tech.501",
        "This feature is not technically supported by this gateway",
    )

    with patch_get_vehicle_data() as patches:
        for value in patches.values():
            value.side_effect = not_supported_exception
        yield patches
