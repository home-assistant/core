"""Tests for the Midea water heater platform."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.c3 import C3SilentLevel, DeviceAttributes as C3Attributes
from midealocal.devices.cd import DeviceAttributes as CDAttributes
from midealocal.devices.e2 import DeviceAttributes as E2Attributes
from midealocal.devices.e3 import DeviceAttributes as E3Attributes
from midealocal.devices.e6 import DeviceAttributes as E6Attributes
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import (
    ATTR_AWAY_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


def _c3_device() -> DummyDevice:
    return DummyDevice(
        DeviceType.C3,
        attributes={
            C3Attributes.zone1_power: False,
            C3Attributes.zone2_power: False,
            C3Attributes.dhw_power: False,
            C3Attributes.zone1_curve: False,
            C3Attributes.zone2_curve: False,
            C3Attributes.disinfect: False,
            C3Attributes.fast_dhw: False,
            C3Attributes.zone_temp_type: [False, False],
            C3Attributes.zone1_room_temp_mode: False,
            C3Attributes.zone2_room_temp_mode: False,
            C3Attributes.zone1_water_temp_mode: False,
            C3Attributes.zone2_water_temp_mode: False,
            C3Attributes.silent_mode: False,
            C3Attributes.silent_level: C3SilentLevel.OFF.name.lower(),
            C3Attributes.eco_mode: False,
            C3Attributes.tbh: False,
            C3Attributes.mode: 1,
            C3Attributes.mode_auto: 1,
            C3Attributes.zone_target_temp: [25.0, 25.0],
            C3Attributes.dhw_target_temp: 25.0,
            C3Attributes.room_target_temp: 30.0,
            C3Attributes.zone_heating_temp_max: [55.0, 55.0],
            C3Attributes.zone_heating_temp_min: [25.0, 25.0],
            C3Attributes.zone_cooling_temp_max: [25.0, 25.0],
            C3Attributes.zone_cooling_temp_min: [5.0, 5.0],
            C3Attributes.room_temp_max: 60.0,
            C3Attributes.room_temp_min: 34.0,
            C3Attributes.dhw_temp_max: 60.0,
            C3Attributes.dhw_temp_min: 20.0,
            C3Attributes.tank_actual_temperature: None,
            C3Attributes.target_temperature: [25.0, 25.0],
            C3Attributes.temperature_max: [0.0, 0.0],
            C3Attributes.temperature_min: [0.0, 0.0],
            C3Attributes.total_energy_consumption: None,
            C3Attributes.status_heating: None,
            C3Attributes.status_dhw: None,
            C3Attributes.status_tbh: None,
            C3Attributes.status_ibh: None,
            C3Attributes.total_produced_energy: None,
            C3Attributes.outdoor_temperature: None,
            C3Attributes.temp_tw_in: None,
            C3Attributes.temp_tw_out: None,
            C3Attributes.instant_power0: None,
            C3Attributes.error_code: 0,
        },
    )


def _cd_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.CD,
        attributes={
            CDAttributes.power: True,
            CDAttributes.mode: "standard",
            CDAttributes.max_temperature: 65.0,
            CDAttributes.min_temperature: 35.0,
            CDAttributes.target_temperature: 40.0,
            CDAttributes.current_temperature: 41.0,
            CDAttributes.outdoor_temperature: 25.0,
            CDAttributes.condenser_temperature: 23.0,
            CDAttributes.compressor_temperature: 30.0,
            CDAttributes.compressor_status: None,
            CDAttributes.water_level: None,
            CDAttributes.fahrenheit: False,
            CDAttributes.heat: None,
            CDAttributes.dual_heat: None,
            CDAttributes.elec_heat: None,
            CDAttributes.top_elec_heat: None,
            CDAttributes.bottom_elec_heat: None,
            CDAttributes.water_pump: None,
            CDAttributes.four_way: None,
            CDAttributes.back_water: None,
            CDAttributes.sterilize: None,
            CDAttributes.disinfect: None,
            CDAttributes.disinfection_temperature: None,
            CDAttributes.top_temperature: None,
            CDAttributes.bottom_temperature: None,
            CDAttributes.wind: None,
            CDAttributes.eco: None,
            CDAttributes.smart_grid: None,
            CDAttributes.multi_terminal: None,
            CDAttributes.mute_effect: None,
            CDAttributes.mute_status: None,
            CDAttributes.maintenance_reminder: None,
            CDAttributes.maintain_warn_tag: None,
            CDAttributes.maintain_warn: None,
            CDAttributes.error_code: None,
            CDAttributes.typeinfo: None,
            CDAttributes.vacation_mode: False,
            CDAttributes.vacation_days: 0,
            CDAttributes.vacation_temperature: None,
            CDAttributes.vacation_start_year: None,
            CDAttributes.vacation_start_month: None,
            CDAttributes.vacation_start_day: None,
            CDAttributes.order1_effect: None,
            CDAttributes.order2_effect: None,
            CDAttributes.auto_sterilize_week: None,
            CDAttributes.auto_sterilize_hour: None,
            CDAttributes.auto_sterilize_minute: None,
            CDAttributes.weekly_effects: None,
            CDAttributes.weekly_schedule: None,
            CDAttributes.daily_timer_schedule: None,
        },
    )
    device.preset_modes = [
        "none",
        "energy_save",
        "standard",
        "dual",
        "smart",
    ]
    return device


def _e2_device() -> DummyDevice:
    return DummyDevice(
        DeviceType.E2,
        attributes={
            E2Attributes.power: True,
            E2Attributes.heating: True,
            E2Attributes.keep_warm: True,
            E2Attributes.protection: False,
            E2Attributes.temperature_max: 75.0,
            E2Attributes.temperature_min: 30.0,
            E2Attributes.current_temperature: 21.0,
            E2Attributes.target_temperature: 40.0,
            E2Attributes.whole_tank_heating: True,
            E2Attributes.variable_heating: True,
            E2Attributes.heating_time_remaining: 50,
            E2Attributes.water_consumption: None,
            E2Attributes.heating_power: None,
            E2Attributes.fast_hot_power: None,
            E2Attributes.water_flow: None,
            E2Attributes.sterilization: None,
            E2Attributes.heat_water_level: None,
            E2Attributes.eplus: None,
            E2Attributes.memory: None,
            E2Attributes.fast_wash: None,
            E2Attributes.half_heat: None,
            E2Attributes.summer: None,
            E2Attributes.winter: None,
            E2Attributes.efficient: None,
            E2Attributes.night: None,
            E2Attributes.screen_off: None,
            E2Attributes.sleep: None,
            E2Attributes.cloud: None,
            E2Attributes.appoint_wash: None,
            E2Attributes.now_wash: None,
            E2Attributes.smart_sterilize: None,
            E2Attributes.sterilize_high_temp: None,
            E2Attributes.uv_sterilize: None,
            E2Attributes.discharge_status: None,
            E2Attributes.top_temp: None,
            E2Attributes.bottom_heat: None,
            E2Attributes.top_heat: None,
            E2Attributes.water_cyclic: None,
            E2Attributes.water_system: None,
            E2Attributes.in_temperature: None,
            E2Attributes.day_water_consumption: None,
            E2Attributes.volume: None,
            E2Attributes.rate: None,
        },
    )


def _e3_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.E3,
        attributes={
            E3Attributes.power: False,
            E3Attributes.burning_state: False,
            E3Attributes.zero_cold_water: False,
            E3Attributes.protection: False,
            E3Attributes.zero_cold_pulse: False,
            E3Attributes.smart_volume: False,
            E3Attributes.current_temperature: 38.0,
            E3Attributes.target_temperature: 40.0,
            E3Attributes.temperature_min: 35.0,
            E3Attributes.temperature_max: 65.0,
        },
    )
    device.precision_halves = True
    return device


def _e6_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.E6,
        attributes={
            E6Attributes.main_power: False,
            E6Attributes.heating_power: True,
            E6Attributes.heating_working: None,
            E6Attributes.bathing_working: None,
            E6Attributes.temperature_min: [30.0, 35.0],
            E6Attributes.temperature_max: [80.0, 60.0],
            E6Attributes.heating_temperature: 50.0,
            E6Attributes.bathing_temperature: 40.0,
            E6Attributes.heating_leaving_temperature: None,
            E6Attributes.bathing_leaving_temperature: None,
            E6Attributes.cold_water_single: None,
            E6Attributes.cold_water_dot: None,
            E6Attributes.heating_modes: None,
        },
    )
    device.preset_modes = [
        "normal",
        "out",
        "home",
        "sleep",
    ]
    return device


async def _assert_service_calls(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    service_data: dict,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call a water heater service and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )
    assert device.calls == expected_calls


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(
            _c3_device(),
            id="c3",
        ),
        pytest.param(
            _cd_device(),
            id="cd",
        ),
        pytest.param(
            _e2_device(),
            id="e2",
        ),
        pytest.param(
            _e3_device(),
            id="e3",
        ),
        pytest.param(
            _e6_device(),
            id="e6",
        ),
    ],
)
async def test_midea_water_heater_default_state(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    device: DummyDevice,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test water heater entities are created and service calls reach the device."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.WATER_HEATER]):
        await setup_integration(hass, config_entry, device)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("device", "services", "services_data", "expected_calls", "entity_suffix"),
    [
        pytest.param(
            _c3_device(),
            [
                SERVICE_TURN_OFF,
                SERVICE_TURN_ON,
                SERVICE_SET_TEMPERATURE,
            ],
            [
                {},
                {},
                {ATTR_TEMPERATURE: 50.0},
            ],
            [
                [("set_attribute", C3Attributes.dhw_power, False)],
                [("set_attribute", C3Attributes.dhw_power, True)],
                [("set_attribute", C3Attributes.dhw_target_temp, 50.0)],
            ],
            "water_heater",
            id="c3",
        ),
        pytest.param(
            _cd_device(),
            [
                SERVICE_TURN_OFF,
                SERVICE_TURN_ON,
                SERVICE_SET_TEMPERATURE,
            ],
            [
                {},
                {},
                {ATTR_TEMPERATURE: 50.0},
            ],
            [
                [("set_attribute", CDAttributes.power, False)],
                [("set_attribute", CDAttributes.power, True)],
                [("set_attribute", CDAttributes.target_temperature, 50.0)],
            ],
            "water_heater",
            id="cd",
        ),
        pytest.param(
            _e2_device(),
            [
                SERVICE_TURN_OFF,
                SERVICE_TURN_ON,
                SERVICE_SET_TEMPERATURE,
            ],
            [
                {},
                {},
                {ATTR_TEMPERATURE: 50.0},
            ],
            [
                [("set_attribute", E2Attributes.power, False)],
                [("set_attribute", E2Attributes.power, True)],
                [("set_attribute", E2Attributes.target_temperature, 50.0)],
            ],
            "water_heater",
            id="e2",
        ),
        pytest.param(
            _e3_device(),
            [
                SERVICE_TURN_OFF,
                SERVICE_TURN_ON,
                SERVICE_SET_TEMPERATURE,
            ],
            [
                {},
                {},
                {ATTR_TEMPERATURE: 50.0},
            ],
            [
                [("set_attribute", E3Attributes.power, False)],
                [("set_attribute", E3Attributes.power, True)],
                [("set_attribute", E3Attributes.target_temperature, 50.0)],
            ],
            "water_heater",
            id="e3",
        ),
        pytest.param(
            _e6_device(),
            [
                SERVICE_TURN_OFF,
                SERVICE_TURN_ON,
                SERVICE_SET_TEMPERATURE,
                SERVICE_SET_AWAY_MODE,
                SERVICE_SET_AWAY_MODE,
            ],
            [
                {},
                {},
                {ATTR_TEMPERATURE: 50.0},
                {ATTR_AWAY_MODE: True},
                {ATTR_AWAY_MODE: False},
            ],
            [
                [
                    ("set_attribute", E6Attributes.heating_power, False),
                ],
                [
                    ("set_attribute", E6Attributes.heating_power, True),
                ],
                [
                    ("set_attribute", E6Attributes.heating_temperature, 50.0),
                ],
                [
                    ("set_attribute", E6Attributes.heating_modes, "out"),
                ],
                [
                    ("set_attribute", E6Attributes.heating_modes, "normal"),
                ],
            ],
            "water_heater_heating",
            id="e6_heating",
        ),
        pytest.param(
            _e6_device(),
            [
                SERVICE_TURN_OFF,
                SERVICE_TURN_ON,
                SERVICE_SET_TEMPERATURE,
            ],
            [
                {},
                {},
                {ATTR_TEMPERATURE: 50.0},
            ],
            [
                [
                    ("set_attribute", E6Attributes.main_power, False),
                ],
                [
                    ("set_attribute", E6Attributes.main_power, True),
                ],
                [
                    ("set_attribute", E6Attributes.bathing_temperature, 50.0),
                ],
            ],
            "water_heater_bathing",
            id="e6_bathing",
        ),
    ],
)
async def test_midea_water_heater_services(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    device: DummyDevice,
    services: list[str],
    services_data: list[dict],
    expected_calls: list[list[tuple]],
    entity_suffix: str,
) -> None:
    """Test water heater service calls reach the device."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.WATER_HEATER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[
        f"{TEST_DEVICE_ID}_{entity_suffix}"
    ]
    for i, service in enumerate(services):
        await _assert_service_calls(
            hass,
            entity_entry.entity_id,
            service,
            services_data[i],
            expected_calls[i],
            device,
        )


async def test_e2_min_max_temperature_from_device(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test E2 min/max temperature are read from the device attributes."""
    device = _e2_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)
    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_water_heater"]
    entity = hass.data[WATER_HEATER_DOMAIN].get_entity(entity_entry.entity_id)

    assert entity is not None
    assert entity.min_temp == 30.0
    assert entity.max_temp == 75.0


async def test_e3_min_max_temperature_from_device(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test E3 min/max temperature are read from the device attributes."""
    device = _e3_device()
    config_entry = mock_config_entry(device)
    await setup_integration(hass, config_entry, device)
    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_water_heater"]
    entity = hass.data[WATER_HEATER_DOMAIN].get_entity(entity_entry.entity_id)

    assert entity is not None
    assert entity.min_temp == 35.0
    assert entity.max_temp == 65.0
