"""Test the Tesla Fleet services."""

from unittest.mock import patch

from probatio import MultipleInvalid
import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.services import (
    ATTR_DESTINATION,
    ATTR_GPS,
    ATTR_ORDER,
    SERVICE_NAVIGATION_GPS_REQUEST,
    SERVICE_NAVIGATION_REQUEST,
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


async def test_navigation_request(
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
            SERVICE_NAVIGATION_REQUEST,
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


@pytest.mark.parametrize(
    ("service_data", "expected_order"),
    [({}, 1), ({ATTR_ORDER: 3}, 3)],
)
async def test_navigation_gps_request(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    service_data: dict[str, int],
    expected_order: int,
) -> None:
    """Test sending coordinates to the vehicle."""
    await setup_platform(hass, normal_config_entry)

    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.navigation_gps_request",
        return_value=COMMAND_OK,
    ) as navigation_gps_request:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATION_GPS_REQUEST,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_GPS: {CONF_LATITUDE: LAT, CONF_LONGITUDE: LON},
                **service_data,
            },
            blocking=True,
        )
    navigation_gps_request.assert_called_once_with(
        lat=LAT, lon=LON, order=expected_order
    )


@pytest.mark.parametrize("order", [0, 4])
async def test_navigation_gps_request_invalid_order(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    order: int,
) -> None:
    """Test an order outside the supported range is rejected."""
    await setup_platform(hass, normal_config_entry)

    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATION_GPS_REQUEST,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_GPS: {CONF_LATITUDE: LAT, CONF_LONGITUDE: LON},
                ATTR_ORDER: order,
            },
            blocking=True,
        )


async def test_navigation_request_command_error(
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
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATION_REQUEST,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_DESTINATION: "Home",
            },
            blocking=True,
        )


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
            SERVICE_NAVIGATION_REQUEST,
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
            SERVICE_NAVIGATION_REQUEST,
            {CONF_DEVICE_ID: device.id, ATTR_DESTINATION: "Home"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "no_vehicle_data_for_device"


async def test_unknown_device(
    hass: HomeAssistant, normal_config_entry: MockConfigEntry
) -> None:
    """Test services reject an unknown device."""
    await setup_platform(hass, normal_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATION_GPS_REQUEST,
            {
                CONF_DEVICE_ID: "nope",
                ATTR_GPS: {CONF_LATITUDE: LAT, CONF_LONGITUDE: LON},
            },
            blocking=True,
        )
