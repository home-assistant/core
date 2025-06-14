"""Test the Tesla Fleet button platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import NotOnWhitelistFault

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import ServiceValidationError

from . import assert_entities, setup_platform
from .const import COMMAND_OK, VEHICLE_DATA

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.services import (
    SERVICE_NAVIGATION_REQUEST,
    SERVICE_NAVIGATION_GPS_REQUEST,
    SERVICE_NAVIGATE_TO_SUPERCHARGER_REQUEST,
    SERVICE_SHARE_TO_VEHICLE,
    ATTR_DEVICE_ID,
    ATTR_SUPERCHARGER_ID,
    ATTR_VALUE,
    ATTR_LOCATION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE
)

from tests.common import MockConfigEntry

@pytest.mark.parametrize(
    ("service", "func", "service_data"),
    [
        (SERVICE_NAVIGATE_TO_SUPERCHARGER_REQUEST, "navigation_sc_request", {ATTR_SUPERCHARGER_ID: "12345"}),
        (SERVICE_NAVIGATION_GPS_REQUEST, "navigation_gps_request", {ATTR_LOCATION: {ATTR_LATITUDE: 37.7749, ATTR_LONGITUDE: -122.4194}}),
        (SERVICE_NAVIGATION_REQUEST, "navigation_request", {ATTR_VALUE: "Test Location"}),
        (SERVICE_SHARE_TO_VEHICLE, "navigation_request", {ATTR_VALUE: "https://example.com"})
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_services(
    hass: HomeAssistant, normal_config_entry: MockConfigEntry, service: str, func: str, service_data: dict[str, str | float | int | None]
) -> None:
    """Tests that the custom services are correct."""
    
    await setup_platform(hass, normal_config_entry)
    
    # Find the specific Tesla vehicle device from the registry
    device_registry = dr.async_get(hass)
    expected_vin = VEHICLE_DATA["response"]["vin"] # Get VIN from the imported const

    vehicle_device_id: str | None = None
    for device_entry in device_registry.devices.values():
        # Check if any identifier tuple (domain, value) matches our domain and VIN
        if device_entry.identifiers and any(
            identifier == (DOMAIN, expected_vin) for identifier in device_entry.identifiers
        ):
            vehicle_device_id = device_entry.id
            break
    
    assert vehicle_device_id, f"No Tesla vehicle device found with VIN {expected_vin} in registry"
    vehicle_device = vehicle_device_id

    with patch(
        f"tesla_fleet_api.tesla.VehicleFleet.{func}",
        return_value=COMMAND_OK,
    ) as command:
        await hass.services.async_call(
            DOMAIN,
            service,
            {
                ATTR_DEVICE_ID: vehicle_device,
                **service_data,
            },
            blocking=True
        )
        command.assert_called_once()


async def test_service_validation_errors(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry
) -> None:
    """Tests that the custom services handle bad data."""

    await setup_platform(hass, normal_config_entry)

    # Bad device ID
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATION_GPS_REQUEST,
            {
                ATTR_DEVICE_ID: "nope",
                ATTR_LOCATION: {ATTR_LATITUDE: 37.7749, ATTR_LONGITUDE: -122.4194},
            },
            blocking=True,
        )