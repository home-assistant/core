"""Test the Tesla Fleet services."""

from unittest.mock import patch

import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.services import (
    ATTR_DESTINATION,
    ATTR_GPS,
    SERVICE_NAVIGATE_TO_COORDINATES,
    SERVICE_NAVIGATE_TO_DESTINATION,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .const import COMMAND_ERROR, COMMAND_OK, VEHICLE_DATA

from tests.common import MockConfigEntry

LAT = -27.9699373
LON = 153.3726526


def get_vehicle_device_id(
    device_registry: dr.DeviceRegistry, config_entry: MockConfigEntry
) -> str:
    """Return the device registry ID of the test vehicle."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, VEHICLE_DATA["response"]["vin"]), config_entry.entry_id
    )
    assert device
    return device.id


async def test_navigate_to_destination(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sending a destination to the vehicle."""
    await setup_platform(hass, normal_config_entry)

    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.navigation_request",
        return_value=COMMAND_OK,
    ) as navigation_request:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_DESTINATION,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_DESTINATION: "1600 Amphitheatre Parkway, Mountain View, CA",
            },
            blocking=True,
        )
    navigation_request.assert_called_once_with(
        "1600 Amphitheatre Parkway, Mountain View, CA"
    )


async def test_navigate_to_coordinates(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test sending coordinates to the vehicle."""
    await setup_platform(hass, normal_config_entry)

    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.navigation_gps_request",
        return_value=COMMAND_OK,
    ) as navigation_gps_request:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_COORDINATES,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_GPS: {CONF_LATITUDE: LAT, CONF_LONGITUDE: LON},
            },
            blocking=True,
        )
    navigation_gps_request.assert_called_once_with(lat=LAT, lon=LON)


async def test_navigate_to_destination_command_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a command error from the vehicle is raised."""
    await setup_platform(hass, normal_config_entry)

    with (
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_request",
            return_value=COMMAND_ERROR,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_DESTINATION,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_DESTINATION: "Home",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "command_error"


async def test_missing_vehicle_cmds_scope(
    hass: HomeAssistant,
    readonly_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test services refuse to run without the vehicle commands scope."""
    await setup_platform(hass, readonly_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_DESTINATION,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, readonly_config_entry
                ),
                ATTR_DESTINATION: "Home",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "missing_scope_vehicle_cmds"


async def test_energy_site_device(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test services reject a device that is not a vehicle."""
    await setup_platform(hass, normal_config_entry)

    energy_site = normal_config_entry.runtime_data.energysites[0]
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(energy_site.id)), normal_config_entry.entry_id
    )
    assert device

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_DESTINATION,
            {CONF_DEVICE_ID: device.id, ATTR_DESTINATION: "Home"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "no_vehicle_data_for_device"


async def test_unknown_device(
    hass: HomeAssistant, normal_config_entry: MockConfigEntry
) -> None:
    """Test services reject an unknown device."""
    await setup_platform(hass, normal_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_COORDINATES,
            {
                CONF_DEVICE_ID: "nope",
                ATTR_GPS: {CONF_LATITUDE: LAT, CONF_LONGITUDE: LON},
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_device_not_found"
