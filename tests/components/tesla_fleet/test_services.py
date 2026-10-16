"""Test the Tesla Fleet services."""

import asyncio
from unittest.mock import patch

import probatio
import pytest

from homeassistant.components.tesla_fleet.const import DOMAIN
from homeassistant.components.tesla_fleet.models import TeslaFleetVehicleData
from homeassistant.components.tesla_fleet.services import (
    ATTR_DESTINATION,
    ATTR_GPS,
    ATTR_PLACE_IDS,
    SERVICE_NAVIGATE_TO_COORDINATES,
    SERVICE_NAVIGATE_TO_DESTINATION,
    SERVICE_NAVIGATE_TO_WAYPOINTS,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .const import COMMAND_ERROR, COMMAND_OK, COMMAND_REASON, VEHICLE_DATA

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


@pytest.mark.parametrize(
    ("place_ids", "encoded"),
    [
        pytest.param(
            ["ChIJ_first", "GhIJ_final"],
            "refId:ChIJ_first,refId:GhIJ_final",
            id="ordered-stops",
        ),
        pytest.param(["GhIJ_single"], "refId:GhIJ_single", id="one-place"),
        pytest.param(
            ["ID_A", "ID_B", "ID_A"],
            "refId:ID_A,refId:ID_B,refId:ID_A",
            id="return-trip",
        ),
        pytest.param(["Eic" + "x" * 1024], "refId:Eic" + "x" * 1024, id="long-id"),
    ],
)
async def test_navigate_to_waypoints(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    place_ids: list[str],
    encoded: str,
) -> None:
    """Test forwarding caller-supplied Place IDs without rewriting the trip."""
    await setup_platform(hass, normal_config_entry)
    with patch(
        "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request",
        return_value=COMMAND_OK,
    ) as navigation_waypoints_request:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_PLACE_IDS: place_ids,
            },
            blocking=True,
        )
    navigation_waypoints_request.assert_awaited_once_with(encoded)


@pytest.mark.parametrize(
    "place_ids",
    [
        pytest.param([], id="empty-list"),
        pytest.param("ID_A", id="scalar"),
        pytest.param([42], id="non-string"),
        pytest.param([None], id="null-entry"),
        pytest.param([""], id="empty-entry"),
        pytest.param([" "], id="whitespace"),
        pytest.param(["ID A"], id="internal-space"),
        pytest.param(["ID_A\n"], id="trailing-newline"),
        pytest.param(["ID_A,ID_B"], id="delimiter"),
        pytest.param(["refId:ID_A"], id="already-prefixed"),
    ],
)
async def test_navigate_to_waypoints_invalid_input(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    place_ids: list[str | int | None] | str,
) -> None:
    """Reject malformed input before waking or sending navigation."""
    await setup_platform(hass, normal_config_entry)
    with (
        patch("homeassistant.components.tesla_fleet.services.wake_up_vehicle") as wake,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request"
        ) as command,
        pytest.raises(probatio.Invalid),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_PLACE_IDS: place_ids,
            },
            blocking=True,
        )
    wake.assert_not_awaited()
    command.assert_not_awaited()


async def test_navigate_to_waypoints_missing_place_ids(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Require an explicit itinerary before interacting with the vehicle."""
    await setup_platform(hass, normal_config_entry)
    with (
        patch("homeassistant.components.tesla_fleet.services.wake_up_vehicle") as wake,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request"
        ) as command,
        pytest.raises(probatio.Invalid),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                )
            },
            blocking=True,
        )
    wake.assert_not_awaited()
    command.assert_not_awaited()


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


@pytest.mark.parametrize(
    ("result", "translation_key"),
    [
        pytest.param(COMMAND_ERROR, "command_error", id="api-error"),
        pytest.param(COMMAND_REASON, "command_reason", id="vehicle-refusal"),
    ],
)
async def test_navigate_to_waypoints_command_error(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    result: dict[str, object],
    translation_key: str,
) -> None:
    """Surface the established navigation command errors."""
    await setup_platform(hass, normal_config_entry)
    with (
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request",
            return_value=result,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_PLACE_IDS: ["ID_A"],
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == translation_key


async def test_navigate_to_waypoints_wake_before_command(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Wait for wake completion before sending the itinerary."""
    await setup_platform(hass, normal_config_entry)
    wake_started = asyncio.Event()
    release_wake = asyncio.Event()
    wake_completed = asyncio.Event()

    async def wait_for_wake(_vehicle: TeslaFleetVehicleData) -> None:
        wake_started.set()
        await release_wake.wait()
        wake_completed.set()

    async def send_waypoints(waypoints: str) -> dict[str, object]:
        assert wake_completed.is_set()
        assert waypoints == "refId:ID_A"
        return COMMAND_OK

    with (
        patch(
            "homeassistant.components.tesla_fleet.services.wake_up_vehicle",
            side_effect=wait_for_wake,
        ) as wake,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request",
            side_effect=send_waypoints,
        ) as command,
    ):
        run = asyncio.create_task(
            hass.services.async_call(
                DOMAIN,
                SERVICE_NAVIGATE_TO_WAYPOINTS,
                {
                    CONF_DEVICE_ID: get_vehicle_device_id(
                        device_registry, normal_config_entry
                    ),
                    ATTR_PLACE_IDS: ["ID_A"],
                },
                blocking=True,
            )
        )
        try:
            await asyncio.wait_for(wake_started.wait(), timeout=1)
            assert not wake_completed.is_set()
            command.assert_not_awaited()
            release_wake.set()
            await asyncio.wait_for(run, timeout=1)
        finally:
            release_wake.set()
            run.cancel()
            await asyncio.gather(run, return_exceptions=True)
    wake.assert_awaited_once()
    command.assert_awaited_once_with("refId:ID_A")


async def test_navigate_to_waypoints_wake_failure(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Do not send navigation when vehicle wake fails."""
    await setup_platform(hass, normal_config_entry)
    with (
        patch(
            "homeassistant.components.tesla_fleet.services.wake_up_vehicle",
            side_effect=HomeAssistantError(
                translation_domain=DOMAIN, translation_key="wake_up_timeout"
            ),
        ),
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request"
        ) as command,
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, normal_config_entry
                ),
                ATTR_PLACE_IDS: ["ID_A"],
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "wake_up_timeout"
    command.assert_not_awaited()


@pytest.mark.parametrize(
    ("service_name", "service_data"),
    [
        pytest.param(
            SERVICE_NAVIGATE_TO_DESTINATION,
            {ATTR_DESTINATION: "Home"},
            id="destination",
        ),
        pytest.param(
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {ATTR_PLACE_IDS: ["ID_A"]},
            id="waypoints",
        ),
    ],
)
async def test_missing_vehicle_cmds_scope(
    hass: HomeAssistant,
    readonly_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    service_name: str,
    service_data: dict[str, str | list[str]],
) -> None:
    """Test services refuse to run without the vehicle commands scope."""
    await setup_platform(hass, readonly_config_entry)
    with (
        patch("homeassistant.components.tesla_fleet.services.wake_up_vehicle") as wake,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request"
        ) as command,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {
                CONF_DEVICE_ID: get_vehicle_device_id(
                    device_registry, readonly_config_entry
                ),
                **service_data,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "missing_scope_vehicle_cmds"
    wake.assert_not_awaited()
    command.assert_not_awaited()


@pytest.mark.parametrize(
    ("service_name", "service_data"),
    [
        pytest.param(
            SERVICE_NAVIGATE_TO_DESTINATION,
            {ATTR_DESTINATION: "Home"},
            id="destination",
        ),
        pytest.param(
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {ATTR_PLACE_IDS: ["ID_A"]},
            id="waypoints",
        ),
    ],
)
async def test_energy_site_device(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    service_name: str,
    service_data: dict[str, str | list[str]],
) -> None:
    """Test services reject a device that is not a vehicle."""
    await setup_platform(hass, normal_config_entry)

    energy_site = normal_config_entry.runtime_data.energysites[0]
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(energy_site.id)), normal_config_entry.entry_id
    )
    assert device

    with (
        patch("homeassistant.components.tesla_fleet.services.wake_up_vehicle") as wake,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request"
        ) as command,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {CONF_DEVICE_ID: device.id, **service_data},
            blocking=True,
        )
    assert exc_info.value.translation_key == "no_vehicle_data_for_device"
    wake.assert_not_awaited()
    command.assert_not_awaited()


@pytest.mark.parametrize(
    ("service_name", "service_data"),
    [
        pytest.param(
            SERVICE_NAVIGATE_TO_COORDINATES,
            {ATTR_GPS: {CONF_LATITUDE: LAT, CONF_LONGITUDE: LON}},
            id="coordinates",
        ),
        pytest.param(
            SERVICE_NAVIGATE_TO_WAYPOINTS,
            {ATTR_PLACE_IDS: ["ID_A"]},
            id="waypoints",
        ),
    ],
)
async def test_unknown_device(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    service_name: str,
    service_data: dict[str, list[str] | dict[str, float]],
) -> None:
    """Test services reject an unknown device."""
    await setup_platform(hass, normal_config_entry)
    with (
        patch("homeassistant.components.tesla_fleet.services.wake_up_vehicle") as wake,
        patch(
            "tesla_fleet_api.tesla.VehicleFleet.navigation_waypoints_request"
        ) as command,
        pytest.raises(ServiceValidationError) as exc_info,
    ):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            {CONF_DEVICE_ID: "nope", **service_data},
            blocking=True,
        )
    assert exc_info.value.translation_key == "service_device_not_found"
    wake.assert_not_awaited()
    command.assert_not_awaited()
