"""Tests for midea climate.py."""

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
    ATTR_OPERATION_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
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
    """Call a climate service and assert the fake device recorded the right call."""
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
    ("device", "services", "services_data", "expected_calls", "entity_sufix"),
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
                SERVICE_SET_TEMPERATURE,
                SERVICE_SET_OPERATION_MODE,
                SERVICE_SET_OPERATION_MODE,
            ],
            [
                {ATTR_TEMPERATURE: 50.0},
                {ATTR_OPERATION_MODE: "standard"},
                {ATTR_OPERATION_MODE: "none"},
            ],
            [
                [("set_attribute", CDAttributes.target_temperature, 50.0)],
                [("set_attribute", CDAttributes.mode, "standard")],
                [("set_attribute", CDAttributes.mode, "none")],
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
                SERVICE_SET_OPERATION_MODE,
            ],
            [
                {},
                {},
                {ATTR_TEMPERATURE: 50.0},
                {ATTR_OPERATION_MODE: "home"},
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
                    ("set_attribute", E6Attributes.heating_modes, "home"),
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
    entity_sufix: str,
) -> None:
    """Test water heater service calls reach the device."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.WATER_HEATER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[
        f"{TEST_DEVICE_ID}_{entity_sufix}"
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


# async def test_midea_cc_climate_setup_and_services(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test CC climate entities are created and exposed through hass.states."""
#     device = DummyDevice(
#         DeviceType.CC,
#         attributes={
#             CCAttributes.power: True,
#             CCAttributes.mode: 5,
#             CCAttributes.fan_speed: "High",
#             CCAttributes.temperature_precision: 0.5,
#             CCAttributes.swing: True,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     state = hass.states.get(entity_entry.entity_id)
#     assert state is not None
#     assert state.state == HVACMode.AUTO
#     assert state.attributes[ATTR_FAN_MODE] == "High"
#     assert state.attributes[ATTR_HVAC_MODES] == [
#         HVACMode.OFF,
#         HVACMode.FAN_ONLY,
#         HVACMode.DRY,
#         HVACMode.HEAT,
#         HVACMode.COOL,
#         HVACMode.AUTO,
#     ]
#     assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
#     assert state.attributes[ATTR_SWING_MODE] == SWING_ON
#     assert state.attributes[ATTR_TARGET_TEMP_STEP] == 0.5

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_FAN_MODE,
#         {ATTR_FAN_MODE: "Low"},
#         [("set_attribute", CCAttributes.fan_speed, "Low")],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_SWING_MODE,
#         {ATTR_SWING_MODE: SWING_ON},
#         [("set_attribute", CCAttributes.swing, True)],
#         device,
#     )


# async def test_midea_cf_climate_setup_and_services(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test CF climate entities are created and control calls are routed."""
#     device = DummyDevice(
#         DeviceType.CF,
#         attributes={
#             "power": True,
#             "mode": 2,
#             CFAttributes.min_temperature: 16,
#             CFAttributes.max_temperature: 30,
#             CFAttributes.current_temperature: 22,
#             CFAttributes.target_temperature: 20,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     state = hass.states.get(entity_entry.entity_id)
#     assert state is not None
#     assert state.state == HVACMode.COOL
#     assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.0
#     assert state.attributes[ATTR_HVAC_MODES] == [
#         HVACMode.OFF,
#         HVACMode.AUTO,
#         HVACMode.COOL,
#         HVACMode.HEAT,
#     ]
#     assert state.attributes[ATTR_MAX_TEMP] == 30
#     assert state.attributes[ATTR_MIN_TEMP] == 16
#     assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1.0

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_TEMPERATURE,
#         {ATTR_TEMPERATURE: 24.2, "hvac_mode": HVACMode.OFF},
#         [("set_attribute", CFAttributes.power, False)],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.HEAT},
#         [
#             (
#                 "set_target_temperature",
#                 {"target_temperature": 20.0, "mode": 3},
#             )
#         ],
#         device,
#     )


# async def test_midea_c3_climate_setup_and_services(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test C3 climate entities are created and zone-specific services work."""
#     device = DummyDevice(
#         DeviceType.C3,
#         attributes={
#             C3Attributes.zone_temp_type: [True, False],
#             C3Attributes.temperature_min: [16, 17],
#             C3Attributes.temperature_max: [30, 29],
#             C3Attributes.mode: 1,
#             C3Attributes.zone1_power: True,
#             C3Attributes.target_temperature: [22, 23],
#             C3Attributes.temp_tw_out: 21.5,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entries_by_unique_id = entity_entries(hass, config_entry)

#     zone1 = entries_by_unique_id[f"{TEST_DEVICE_ID}_climate_zone1"]
#     zone2 = entries_by_unique_id[f"{TEST_DEVICE_ID}_climate_zone2"]
#     assert zone2.disabled_by == er.RegistryEntryDisabler.INTEGRATION
#     assert hass.states.get(zone2.entity_id) is None

#     state = hass.states.get(zone1.entity_id)
#     assert state is not None
#     assert state.state == HVACMode.AUTO
#     assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.5
#     assert state.attributes[ATTR_HVAC_MODES] == [
#         HVACMode.OFF,
#         HVACMode.AUTO,
#         HVACMode.COOL,
#         HVACMode.HEAT,
#     ]
#     assert state.attributes[ATTR_MAX_TEMP] == 30
#     assert state.attributes[ATTR_MIN_TEMP] == 16
#     assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1.0
#     assert state.attributes[ATTR_TEMPERATURE] == 22.0

#     await _assert_service_calls(
#         hass,
#         zone1.entity_id,
#         SERVICE_SET_TEMPERATURE,
#         {ATTR_TEMPERATURE: 21.4, "hvac_mode": HVACMode.COOL},
#         [
#             (
#                 "set_target_temperature",
#                 {"target_temperature": 21.4, "mode": 2, "zone": 0},
#             )
#         ],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         zone1.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.OFF},
#         [("set_attribute", C3Attributes.zone1_power, False)],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         zone1.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.HEAT},
#         [("set_mode", 0, 3)],
#         device,
#     )


# async def test_midea_fb_climate_setup_and_services(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test FB climate entities are created and preset calls are routed."""
#     device = DummyDevice(
#         DeviceType.FB,
#         attributes={
#             FBAttributes.mode: "Comfort",
#             FBAttributes.power: True,
#             FBAttributes.current_temperature: 20,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     state = hass.states.get(entity_entry.entity_id)
#     assert state is not None
#     assert state.state == HVACMode.HEAT
#     assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
#     assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.OFF, HVACMode.HEAT]
#     assert state.attributes[ATTR_MAX_TEMP] == 35
#     assert state.attributes[ATTR_MIN_TEMP] == 5
#     assert state.attributes[ATTR_PRESET_MODE] == "Comfort"
#     assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1.0

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_TEMPERATURE,
#         {ATTR_TEMPERATURE: 24.2, "hvac_mode": HVACMode.OFF},
#         [("set_attribute", FBAttributes.power, False)],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.HEAT},
#         [("set_attribute", FBAttributes.power, True)],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_PRESET_MODE,
#         {ATTR_PRESET_MODE: "ECO"},
#         [("set_attribute", FBAttributes.mode, "ECO")],
#         device,
#     )


# @pytest.mark.parametrize(
#     ("fan_speed", "expected_fan_mode"),
#     [
#         pytest.param(101, "auto", id="just_above_auto_threshold"),
#         pytest.param(100, "full", id="auto_threshold_falls_to_full"),
#         pytest.param(80, "high", id="full_threshold_falls_to_high"),
#         pytest.param(60, "medium", id="high_threshold_falls_to_medium"),
#         pytest.param(40, "low", id="medium_threshold_falls_to_low"),
#         pytest.param(20, "silent", id="low_threshold_falls_to_silent"),
#         pytest.param(0, "silent", id="silent_fallback"),
#     ],
# )
# async def test_ac_fan_mode_read_thresholds(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
#     fan_speed: int,
#     expected_fan_mode: str,
# ) -> None:
#     """Test AC fan mode read mapping across every numeric bucket boundary."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.fan_speed: fan_speed,
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#             E2Attributes.indoor_humidity: 50,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     assert (state := hass.states.get(entity_entry.entity_id))
#     assert state.attributes[ATTR_FAN_MODE] == expected_fan_mode


# @pytest.mark.parametrize(
#     ("fan_mode", "expected_speed"),
#     [
#         pytest.param(FAN_SILENT, 20, id="silent"),
#         pytest.param(FAN_LOW, 40, id="low"),
#         pytest.param(FAN_MEDIUM, 60, id="medium"),
#         pytest.param(FAN_HIGH, 80, id="high"),
#         pytest.param(FAN_FULL_SPEED, 100, id="full"),
#         pytest.param(FAN_AUTO, 102, id="auto"),
#     ],
# )
# async def test_ac_fan_mode_write_speeds(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
#     fan_mode: str,
#     expected_speed: int,
# ) -> None:
#     """Test AC set_fan_mode writes the numeric speed for every fan mode."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.fan_speed: 103,
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_FAN_MODE,
#         {ATTR_FAN_MODE: fan_mode},
#         [("set_attribute", E2Attributes.fan_speed, expected_speed)],
#         device,
#     )


# async def test_ac_set_temperature_without_hvac_mode(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test set_temperature without hvac_mode leaves the protocol mode unset."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.fan_speed: 103,
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_TEMPERATURE,
#         {ATTR_TEMPERATURE: 23.0},
#         [
#             (
#                 "set_target_temperature",
#                 {"target_temperature": 23.0, "mode": None, "zone": None},
#             )
#         ],
#         device,
#     )


# @pytest.mark.parametrize(
#     ("humidity", "expected_humidity"),
#     [
#         pytest.param(50, 50.0, id="normal"),
#         pytest.param(0, None, id="invalid_zero"),
#         pytest.param(0xFF, None, id="invalid_ff"),
#     ],
# )
# async def test_ac_humidity_filtering(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
#     humidity: int,
#     expected_humidity: float | None,
# ) -> None:
#     """Test AC humidity filtering for invalid sensor values."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.fan_speed: 103,
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#             E2Attributes.indoor_humidity: humidity,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     assert (state := hass.states.get(entity_entry.entity_id))
#     assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == expected_humidity


# async def test_base_set_temperature_without_target_noop(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test set_temperature without ATTR_TEMPERATURE is ignored."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.fan_speed: 103,
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]
#     entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_entry.entity_id)

#     device.calls.clear()
#     assert entity is not None
#     entity.set_temperature()
#     assert device.calls == []


# async def test_set_preset_mode_none_when_already_none_is_noop(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test setting preset mode to none while already none writes nothing."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.comfort_mode: False,
#             E2Attributes.eco_mode: False,
#             E2Attributes.boost_mode: False,
#             E2Attributes.sleep_mode: False,
#             E2Attributes.frost_protect: False,
#             E2Attributes.fan_speed: 103,
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_PRESET_MODE,
#         {ATTR_PRESET_MODE: PRESET_NONE},
#         [],
#         device,
#     )


# async def test_ac_set_hvac_mode_off_calls_power_off(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test AC HVAC off delegates to turn_off."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.fan_speed: 103,
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.OFF},
#         [("set_attribute", E2Attributes.power, False)],
#         device,
#     )


# @pytest.mark.parametrize(
#     ("attributes", "expected_state"),
#     [
#         pytest.param(
#             {
#                 E2Attributes.power: True,
#                 E2Attributes.mode: 999,
#                 E2Attributes.target_temperature: 22.0,
#                 E2Attributes.indoor_temperature: 21.0,
#                 E2Attributes.fan_speed: 103,
#                 E2Attributes.swing_vertical: True,
#                 E2Attributes.swing_horizontal: True,
#             },
#             "unknown",
#             id="invalid_mode",
#         ),
#         pytest.param(
#             {
#                 E2Attributes.power: True,
#                 E2Attributes.mode: 0,
#                 E2Attributes.target_temperature: 22.0,
#                 E2Attributes.indoor_temperature: 21.0,
#                 E2Attributes.fan_speed: 103,
#                 E2Attributes.swing_vertical: True,
#                 E2Attributes.swing_horizontal: True,
#             },
#             "unknown",
#             id="protocol_mode_zero_while_powered_on",
#         ),
#         pytest.param(
#             {
#                 E2Attributes.power: False,
#                 E2Attributes.mode: 1,
#                 E2Attributes.target_temperature: 22.0,
#                 E2Attributes.indoor_temperature: 21.0,
#                 E2Attributes.fan_speed: 103,
#                 E2Attributes.swing_vertical: True,
#                 E2Attributes.swing_horizontal: True,
#             },
#             HVACMode.OFF,
#             id="power_off",
#         ),
#         pytest.param(
#             {
#                 E2Attributes.power: True,
#                 E2Attributes.target_temperature: 22.0,
#                 E2Attributes.indoor_temperature: 21.0,
#                 E2Attributes.fan_speed: 103,
#                 E2Attributes.swing_vertical: True,
#                 E2Attributes.swing_horizontal: True,
#             },
#             "unknown",
#             id="missing_mode",
#         ),
#         pytest.param(
#             {
#                 E2Attributes.mode: 1,
#                 E2Attributes.target_temperature: 22.0,
#                 E2Attributes.indoor_temperature: 21.0,
#                 E2Attributes.fan_speed: 103,
#                 E2Attributes.swing_vertical: True,
#                 E2Attributes.swing_horizontal: True,
#             },
#             "unknown",
#             id="missing_power",
#         ),
#     ],
# )
# async def test_ac_hvac_mode_branches(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
#     attributes: dict[str, Any],
#     expected_state: str,
# ) -> None:
#     """Test AC hvac_mode across power/mode edge cases.

#     Protocol mode 0 is reserved for the OFF entry in hvac_modes and is
#     never sent by the device while powered on; if the sub-protocol decoder
#     reports it anyway it must not be misread as an explicit OFF request.
#     """
#     device = DummyDevice(DeviceType.AC, attributes=attributes)
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     assert (state := hass.states.get(entity_entry.entity_id))
#     assert state.state == expected_state


# async def test_ac_fan_mode_invalid_type_returns_none(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test AC fan_mode returns None for an unexpected attribute type."""
#     device = DummyDevice(
#         DeviceType.AC,
#         attributes={
#             E2Attributes.power: True,
#             E2Attributes.mode: 1,
#             E2Attributes.target_temperature: 22.0,
#             E2Attributes.indoor_temperature: 21.0,
#             E2Attributes.fan_speed: "auto",
#             E2Attributes.swing_vertical: True,
#             E2Attributes.swing_horizontal: True,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     assert (state := hass.states.get(entity_entry.entity_id))
#     assert state.attributes.get(ATTR_FAN_MODE) is None


# async def test_cf_min_max_temperature_from_device(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test CF min/max temperature are read from the device attributes."""
#     device = DummyDevice(
#         DeviceType.CF,
#         attributes={
#             "power": True,
#             "mode": 2,
#             CFAttributes.min_temperature: 5,
#             CFAttributes.max_temperature: 55,
#             CFAttributes.current_temperature: 22,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]
#     entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_entry.entity_id)

#     assert entity is not None
#     assert entity.min_temp == 5.0
#     assert entity.max_temp == 55.0


# async def test_set_temperature_unsupported_hvac_mode_raises(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test set_temperature with an hvac_mode unsupported by the device raises."""
#     device = DummyDevice(
#         DeviceType.CF,
#         attributes={
#             "power": True,
#             "mode": 2,
#             CFAttributes.min_temperature: 16,
#             CFAttributes.max_temperature: 30,
#             CFAttributes.current_temperature: 22,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     device.calls.clear()
#     with pytest.raises(ServiceValidationError):
#         await hass.services.async_call(
#             CLIMATE_DOMAIN,
#             SERVICE_SET_TEMPERATURE,
#             {
#                 ATTR_ENTITY_ID: entity_entry.entity_id,
#                 ATTR_TEMPERATURE: 23.0,
#                 "hvac_mode": HVACMode.DRY,
#             },
#             blocking=True,
#         )
#     assert device.calls == []


# async def test_c3_temperature_fallback_and_turn_on(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test C3 fallback temperatures and turn_on path for zone power."""
#     device = DummyDevice(
#         DeviceType.C3,
#         attributes={
#             C3Attributes.zone_temp_type: [True],
#             C3Attributes.temperature_min: [5, 5],
#             C3Attributes.temperature_max: [55, 55],
#             C3Attributes.mode: 1,
#             C3Attributes.zone1_power: True,
#             C3Attributes.target_temperature: [22],
#             C3Attributes.temp_tw_out: 21.5,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     zone1 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone1"]
#     entity = hass.data[CLIMATE_DOMAIN].get_entity(zone1.entity_id)

#     assert entity is not None
#     assert entity.min_temp == 5.0
#     assert entity.max_temp == 55.0

#     await _assert_service_calls(
#         hass,
#         zone1.entity_id,
#         SERVICE_TURN_ON,
#         {},
#         [("set_attribute", C3Attributes.zone1_power, True)],
#         device,
#     )


# async def test_c3_zero_temperature_limits_use_fallback(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test C3 min/max fall back to defaults when the device reports [0.0, 0.0].

#     Some devices report [0.0, 0.0] for the temperature limits when in
#     water-mode combined with auto/cool, which must not be treated as a
#     valid (and therefore unusable) range.
#     """
#     device = DummyDevice(
#         DeviceType.C3,
#         attributes={
#             C3Attributes.zone_temp_type: [True, False],
#             C3Attributes.temperature_min: [0.0, 0.0],
#             C3Attributes.temperature_max: [0.0, 0.0],
#             C3Attributes.mode: 1,
#             C3Attributes.zone1_power: True,
#             C3Attributes.target_temperature: [22, 23],
#             C3Attributes.temp_tw_out: 21.5,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     zone1 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone1"]
#     entity = hass.data[CLIMATE_DOMAIN].get_entity(zone1.entity_id)

#     assert entity is not None
#     assert entity.min_temp == 5.0
#     assert entity.max_temp == 60.0


# @pytest.mark.usefixtures("entity_registry_enabled_by_default")
# async def test_c3_zero_temperature_limit_uses_fallback_per_zone(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test C3 min/max fall back per zone when only one zone reports 0.0.

#     A zone stuck at 0.0 must fall back independently, even when the other
#     zone reports a valid, populated value.
#     """
#     device = DummyDevice(
#         DeviceType.C3,
#         attributes={
#             C3Attributes.zone_temp_type: [True, False],
#             C3Attributes.temperature_min: [0.0, 10.0],
#             C3Attributes.temperature_max: [0.0, 45.0],
#             C3Attributes.mode: 1,
#             C3Attributes.zone1_power: True,
#             C3Attributes.target_temperature: [22, 23],
#             C3Attributes.temp_tw_out: 21.5,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     zone1 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone1"]
#     zone2 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone2"]
#     entity1 = hass.data[CLIMATE_DOMAIN].get_entity(zone1.entity_id)
#     entity2 = hass.data[CLIMATE_DOMAIN].get_entity(zone2.entity_id)

#     assert entity1 is not None
#     assert entity1.min_temp == 5.0
#     assert entity1.max_temp == 60.0
#     assert entity2 is not None
#     assert entity2.min_temp == 10.0
#     assert entity2.max_temp == 45.0


# async def test_c3_temperature_limit_list_too_short_uses_fallback(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test C3 min/max fall back when the reported list has fewer than 2 entries."""
#     device = DummyDevice(
#         DeviceType.C3,
#         attributes={
#             C3Attributes.zone_temp_type: [True],
#             C3Attributes.temperature_min: [16],
#             C3Attributes.temperature_max: [30],
#             C3Attributes.mode: 1,
#             C3Attributes.zone1_power: True,
#             C3Attributes.target_temperature: [22],
#             C3Attributes.temp_tw_out: 21.5,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     zone1 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone1"]
#     entity = hass.data[CLIMATE_DOMAIN].get_entity(zone1.entity_id)

#     assert entity is not None
#     assert entity.min_temp == 5.0
#     assert entity.max_temp == 60.0


# @pytest.mark.parametrize(
#     ("attributes", "expected_state"),
#     [
#         pytest.param(
#             {
#                 C3Attributes.zone1_power: True,
#                 C3Attributes.mode: 999,
#                 C3Attributes.temp_tw_out: 21.5,
#             },
#             "unknown",
#             id="invalid_mode",
#         ),
#         pytest.param(
#             {
#                 C3Attributes.zone1_power: True,
#                 C3Attributes.mode: 0,
#                 C3Attributes.temp_tw_out: 21.5,
#             },
#             "unknown",
#             id="protocol_mode_zero_while_powered_on",
#         ),
#         pytest.param(
#             {
#                 C3Attributes.zone1_power: False,
#                 C3Attributes.mode: 1,
#                 C3Attributes.temp_tw_out: 21.5,
#             },
#             HVACMode.OFF,
#             id="power_off",
#         ),
#         pytest.param(
#             {
#                 C3Attributes.zone1_power: True,
#                 C3Attributes.temp_tw_out: 21.5,
#             },
#             "unknown",
#             id="missing_mode",
#         ),
#         pytest.param(
#             {
#                 C3Attributes.zone_temp_type: [True],
#                 C3Attributes.mode: 1,
#                 C3Attributes.target_temperature: [22],
#                 C3Attributes.temp_tw_out: 21.5,
#             },
#             "unknown",
#             id="missing_power",
#         ),
#     ],
# )
# async def test_c3_zone_hvac_mode_branches(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
#     attributes: dict[str, Any],
#     expected_state: str,
# ) -> None:
#     """Test C3 zone hvac_mode across power/mode edge cases."""
#     device = DummyDevice(DeviceType.C3, attributes=attributes)
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     zone1 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone1"]

#     assert (state := hass.states.get(zone1.entity_id))
#     assert state.state == expected_state


# async def test_cf_set_hvac_mode_falls_back_to_min_temp(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test CF set_hvac_mode falls back to min_temp when target_temperature is unset."""
#     device = DummyDevice(
#         DeviceType.CF,
#         attributes={
#             "power": True,
#             "mode": 2,
#             CFAttributes.min_temperature: 16,
#             CFAttributes.max_temperature: 30,
#             CFAttributes.current_temperature: 22,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.HEAT},
#         [
#             (
#                 "set_target_temperature",
#                 {"target_temperature": 16.0, "mode": 3},
#             )
#         ],
#         device,
#     )


# async def test_fb_set_hvac_off_calls_turn_off(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test FB HVAC off delegates to turn_off."""
#     device = DummyDevice(
#         DeviceType.FB,
#         attributes={
#             FBAttributes.mode: "Comfort",
#             FBAttributes.power: True,
#             FBAttributes.current_temperature: 20,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.OFF},
#         [("set_attribute", FBAttributes.power, False)],
#         device,
#     )


# async def test_fb_set_temperature_with_heat_mode_turns_on_when_off(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test FB set_temperature turns the device on when off and hvac_mode is heat."""
#     device = DummyDevice(
#         DeviceType.FB,
#         attributes={
#             FBAttributes.mode: "Comfort",
#             FBAttributes.power: False,
#             FBAttributes.current_temperature: 20,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_TEMPERATURE,
#         {ATTR_TEMPERATURE: 25.0, "hvac_mode": HVACMode.HEAT},
#         [
#             ("set_attribute", FBAttributes.power, True),
#             (
#                 "set_target_temperature",
#                 {"target_temperature": 25.0, "mode": 1, "zone": None},
#             ),
#         ],
#         device,
#     )


# async def test_cf_set_hvac_mode_off_calls_turn_off(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test CF set_hvac_mode with OFF delegates to turn_off."""
#     device = DummyDevice(
#         DeviceType.CF,
#         attributes={
#             "power": True,
#             "mode": 2,
#             CFAttributes.min_temperature: 16,
#             CFAttributes.max_temperature: 30,
#             CFAttributes.current_temperature: 22,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     await _assert_service_calls(
#         hass,
#         entity_entry.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.OFF},
#         [("set_attribute", CFAttributes.power, False)],
#         device,
#     )


# async def test_cf_temperature_range_fallback_when_unset(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test CF min/max temperature fall back to defaults when attributes are unset."""
#     device = DummyDevice(
#         DeviceType.CF,
#         attributes={"power": True, "mode": 2, CFAttributes.current_temperature: 22},
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     assert (state := hass.states.get(entity_entry.entity_id))
#     assert state.attributes[ATTR_MIN_TEMP] == 16.0
#     assert state.attributes[ATTR_MAX_TEMP] == 30.0


# async def test_cc_fan_and_swing_invalid_types_return_none(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test CC fan_mode/swing_mode return None for unexpected attribute types."""
#     device = DummyDevice(
#         DeviceType.CC,
#         attributes={
#             CCAttributes.power: True,
#             CCAttributes.mode: 5,
#             CCAttributes.fan_speed: 1,
#             CCAttributes.temperature_precision: 0.5,
#             CCAttributes.swing: "on",
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     assert (state := hass.states.get(entity_entry.entity_id))
#     assert state.attributes.get(ATTR_FAN_MODE) is None
#     assert state.attributes.get(ATTR_SWING_MODE) is None


# @pytest.mark.usefixtures("entity_registry_enabled_by_default")
# async def test_c3_zone2_service_calls_address_zone_two(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test C3 zone2 service calls use zone index 1 and the zone2_power attribute."""
#     device = DummyDevice(
#         DeviceType.C3,
#         attributes={
#             C3Attributes.zone_temp_type: [True, False],
#             C3Attributes.temperature_min: [16, 17],
#             C3Attributes.temperature_max: [30, 29],
#             C3Attributes.mode: 1,
#             C3Attributes.zone1_power: True,
#             C3Attributes.zone2_power: True,
#             C3Attributes.target_temperature: [22, 23],
#             C3Attributes.temp_tw_out: 21.5,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     zone2 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone2"]

#     await _assert_service_calls(
#         hass,
#         zone2.entity_id,
#         SERVICE_SET_TEMPERATURE,
#         {ATTR_TEMPERATURE: 24.0, "hvac_mode": HVACMode.COOL},
#         [
#             (
#                 "set_target_temperature",
#                 {"target_temperature": 24.0, "mode": 2, "zone": 1},
#             )
#         ],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         zone2.entity_id,
#         SERVICE_SET_HVAC_MODE,
#         {"hvac_mode": HVACMode.HEAT},
#         [("set_mode", 1, 3)],
#         device,
#     )
#     await _assert_service_calls(
#         hass,
#         zone2.entity_id,
#         SERVICE_TURN_OFF,
#         {},
#         [("set_attribute", C3Attributes.zone2_power, False)],
#         device,
#     )


# async def test_c3_temperature_fallback_when_attribute_missing(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test C3 min/max/target temperature fall back when attributes are missing."""
#     device = DummyDevice(
#         DeviceType.C3,
#         attributes={
#             C3Attributes.zone1_power: True,
#             C3Attributes.mode: 1,
#             C3Attributes.temp_tw_out: 21.5,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     zone1 = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate_zone1"]
#     entity = hass.data[CLIMATE_DOMAIN].get_entity(zone1.entity_id)

#     assert entity is not None
#     assert entity.min_temp == 5.0
#     assert entity.max_temp == 60.0
#     assert entity.target_temperature is None


# async def test_fb_invalid_attribute_types_return_none(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
# ) -> None:
#     """Test FB preset_mode/hvac_mode return None for unexpected attribute types."""
#     device = DummyDevice(
#         DeviceType.FB,
#         attributes={
#             FBAttributes.mode: 1,
#             FBAttributes.power: "on",
#             FBAttributes.current_temperature: 20,
#         },
#     )
#     config_entry = mock_config_entry(device)
#     await setup_integration(hass, config_entry, device)
#     entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_climate"]

#     assert (state := hass.states.get(entity_entry.entity_id))
#     assert state.attributes.get(ATTR_PRESET_MODE) is None
#     assert state.state == "unknown"


# @pytest.mark.parametrize(
#     "device",
#     [
#         pytest.param(
#             DummyDevice(
#                 DeviceType.AC,
#                 attributes={
#                     E2Attributes.power: True,
#                     E2Attributes.mode: 1,
#                     E2Attributes.target_temperature: 22.0,
#                     E2Attributes.indoor_temperature: 21.0,
#                     E2Attributes.comfort_mode: False,
#                     E2Attributes.eco_mode: False,
#                     E2Attributes.boost_mode: False,
#                     E2Attributes.sleep_mode: False,
#                     E2Attributes.frost_protect: False,
#                     E2Attributes.fan_speed: 103,
#                     E2Attributes.swing_vertical: True,
#                     E2Attributes.swing_horizontal: True,
#                     E2Attributes.indoor_humidity: 50,
#                 },
#             ),
#             id="ac",
#         ),
#         pytest.param(
#             DummyDevice(
#                 DeviceType.CC,
#                 attributes={
#                     CCAttributes.power: True,
#                     CCAttributes.mode: 5,
#                     CCAttributes.fan_speed: "High",
#                     CCAttributes.temperature_precision: 0.5,
#                     CCAttributes.swing: True,
#                 },
#             ),
#             id="cc",
#         ),
#         pytest.param(
#             DummyDevice(
#                 DeviceType.CF,
#                 attributes={
#                     "power": True,
#                     "mode": 2,
#                     CFAttributes.min_temperature: 16,
#                     CFAttributes.max_temperature: 30,
#                     CFAttributes.current_temperature: 22,
#                 },
#             ),
#             id="cf",
#         ),
#         pytest.param(
#             DummyDevice(
#                 DeviceType.C3,
#                 attributes={
#                     C3Attributes.zone_temp_type: [True, False],
#                     C3Attributes.temperature_min: [16, 17],
#                     C3Attributes.temperature_max: [30, 29],
#                     C3Attributes.mode: 1,
#                     C3Attributes.zone1_power: True,
#                     C3Attributes.zone2_power: False,
#                     C3Attributes.target_temperature: [22, 23],
#                     C3Attributes.temp_tw_out: 21.5,
#                 },
#             ),
#             id="c3",
#         ),
#         pytest.param(
#             DummyDevice(
#                 DeviceType.FB,
#                 attributes={
#                     FBAttributes.mode: "Comfort",
#                     FBAttributes.power: True,
#                     FBAttributes.current_temperature: 20,
#                 },
#             ),
#             id="fb",
#         ),
#     ],
# )
# @pytest.mark.usefixtures("entity_registry_enabled_by_default")
# async def test_climate_state_snapshot(
#     hass: HomeAssistant,
#     mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
#     snapshot: SnapshotAssertion,
#     entity_registry: er.EntityRegistry,
#     device: DummyDevice,
# ) -> None:
#     """Test async_setup_entry creates entities for each device type."""
#     config_entry = mock_config_entry(device)
#     with patch("homeassistant.components.midea._PLATFORMS", [Platform.CLIMATE]):
#         await setup_integration(hass, config_entry, device)

#         await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
