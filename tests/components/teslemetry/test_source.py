"""Tests for the Teslemetry command source facades."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from tesla_fleet_api.teslemetry import EnergySite, Vehicle

from homeassistant.components.teslemetry.source import EnergySource, VehicleSource

# Every vehicle command method the entities and services invoke on the facade,
# with an explicit value for every parameter so faithful forwarding is asserted.
VEHICLE_COMMANDS: list[tuple[str, dict[str, Any]]] = [
    ("wake_up", {}),
    ("flash_lights", {}),
    ("honk_horn", {}),
    ("remote_start_drive", {}),
    ("remote_boombox", {"sound": 0}),
    ("trigger_homelink", {"token": "abc", "lat": 1.0, "lon": 2.0}),
    ("auto_conditioning_start", {}),
    ("auto_conditioning_stop", {}),
    ("set_temps", {"driver_temp": 21.0, "passenger_temp": 22.0}),
    ("set_climate_keeper_mode", {"climate_keeper_mode": 1}),
    ("set_bioweapon_mode", {"on": True, "manual_override": False}),
    ("set_cop_temp", {"cop_temp": 30}),
    ("set_cabin_overheat_protection", {"on": True, "fan_only": False}),
    ("window_control", {"command": "vent", "lat": 1.0, "lon": 2.0}),
    ("charge_port_door_open", {}),
    ("charge_port_door_close", {}),
    ("actuate_trunk", {"which_trunk": "front"}),
    ("sun_roof_control", {"state": "vent"}),
    ("door_lock", {}),
    ("door_unlock", {}),
    ("adjust_volume", {"volume": 0.5}),
    ("media_toggle_playback", {}),
    ("media_next_track", {}),
    ("media_prev_track", {}),
    ("set_charging_amps", {"charging_amps": 16}),
    ("set_charge_limit", {"percent": 80}),
    ("remote_seat_heater_request", {"seat_position": 1, "seat_heater_level": 2}),
    ("remote_steering_wheel_heat_level_request", {"level": 1}),
    ("navigation_gps_request", {"lat": 1.0, "lon": 2.0, "order": 0}),
    ("set_scheduled_charging", {"enable": True, "time": 600}),
    (
        "set_scheduled_departure",
        {
            "enable": True,
            "preconditioning_enabled": False,
            "preconditioning_weekdays_only": False,
            "departure_time": 0,
            "off_peak_charging_enabled": False,
            "off_peak_charging_weekdays_only": False,
            "end_off_peak_time": 0,
        },
    ),
    ("set_valet_mode", {"on": True, "password": "1234"}),
    ("speed_limit_activate", {"pin": "1234"}),
    ("speed_limit_deactivate", {"pin": "1234"}),
    (
        "add_charge_schedule",
        {
            "days_of_week": "All",
            "enabled": True,
            "lat": 1.0,
            "lon": 2.0,
            "start_time": 0,
            "end_time": 60,
            "one_time": False,
            "id": 1,
            "name": "Schedule",
        },
    ),
    ("remove_charge_schedule", {"id": 1}),
    (
        "add_precondition_schedule",
        {
            "days_of_week": "All",
            "enabled": True,
            "lat": 1.0,
            "lon": 2.0,
            "precondition_time": 360,
            "id": 1,
            "one_time": False,
            "name": "Schedule",
        },
    ),
    ("remove_precondition_schedule", {"id": 1}),
    ("set_sentry_mode", {"on": True}),
    (
        "remote_auto_seat_climate_request",
        {"auto_seat_position": 1, "auto_climate_on": True},
    ),
    ("remote_auto_steering_wheel_heat_climate_request", {"on": True}),
    ("set_preconditioning_max", {"on": True, "manual_override": False}),
    ("charge_start", {}),
    ("charge_stop", {}),
    ("guest_mode", {"enable": True}),
    ("schedule_software_update", {"offset_sec": 0}),
]

ENERGY_COMMANDS: list[tuple[str, dict[str, Any]]] = [
    ("backup", {"backup_reserve_percent": 20}),
    (
        "off_grid_vehicle_charging_reserve",
        {"off_grid_vehicle_charging_reserve_percent": 20},
    ),
    ("operation", {"default_real_mode": "autonomous"}),
    (
        "grid_import_export",
        {
            "disallow_charge_from_grid_with_solar_installed": False,
            "customer_preferred_export_rule": "battery_ok",
        },
    ),
    ("storm_mode", {"enabled": True}),
    ("time_of_use_settings", {"settings": {"tariff": "content"}}),
]


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [pytest.param(method, kwargs, id=method) for method, kwargs in VEHICLE_COMMANDS],
)
async def test_vehicle_source_forwards_to_cloud(
    method: str, kwargs: dict[str, Any]
) -> None:
    """Test the vehicle source forwards each command to the cloud client."""
    cloud = AsyncMock(spec=Vehicle)
    source = VehicleSource(cloud)

    result = await getattr(source, method)(**kwargs)

    cloud_method = getattr(cloud, method)
    cloud_method.assert_awaited_once_with(**kwargs)
    assert result is cloud_method.return_value


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [pytest.param(method, kwargs, id=method) for method, kwargs in ENERGY_COMMANDS],
)
async def test_energy_source_forwards_to_cloud(
    method: str, kwargs: dict[str, Any]
) -> None:
    """Test the energy source forwards each command to the cloud client."""
    cloud = AsyncMock(spec=EnergySite)
    source = EnergySource(cloud)

    result = await getattr(source, method)(**kwargs)

    cloud_method = getattr(cloud, method)
    cloud_method.assert_awaited_once_with(**kwargs)
    assert result is cloud_method.return_value


def test_vehicle_source_exposes_cloud_client() -> None:
    """Test the vehicle source exposes the wrapped cloud client."""
    cloud = AsyncMock(spec=Vehicle)
    assert VehicleSource(cloud).cloud is cloud


def test_energy_source_exposes_cloud_client() -> None:
    """Test the energy source exposes the wrapped cloud client."""
    cloud = AsyncMock(spec=EnergySite)
    assert EnergySource(cloud).cloud is cloud
