"""Test ZHA climate."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import time, timedelta
import json
from typing import Literal
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockUser, async_fire_time_changed
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from zha.application.platforms.climate.const import HVAC_MODE_2_SYSTEM, SEQ_OF_OPERATION
from zha.exceptions import ZHAException
from zha.quirks import THERMOSTAT_WEEKLY_SCHEDULE
from zha.zigbee.weekly_schedule import WeeklyScheduleCapabilities
import zhaquirks.sinope.thermostat
import zhaquirks.tuya.ts0601_trv
from zigpy.device import ZigbeeDevice
import zigpy.exceptions
import zigpy.profiles
from zigpy.profiles import zha
import zigpy.types
import zigpy.zcl.clusters
from zigpy.zcl.clusters.hvac import Thermostat
from zigpy.zcl.foundation import DefaultResponse, Status

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_LOW,
    FAN_ON,
    PRESET_AWAY,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.schedule.const import WEEKDAY_TO_CONF
from homeassistant.components.zha.const import DOMAIN as ZHA_DOMAIN, ZHAService
from homeassistant.components.zha.helpers import (
    ZHAGatewayProxy,
    get_zha_data,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.components.zha.weekly_schedule import (
    CONF_WEEKLY_SCHEDULE_LINKS,
    ISSUE_LINK_BROKEN,
    ISSUE_SYNC_FAILED,
    RETRY_DELAY,
    SYNC_COOLDOWN,
    ScheduleConversionError,
    schedule_to_transitions,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import (
    entity_platform,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import find_entity_id, send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

CLIMATE = {
    1: {
        SIG_EP_PROFILE: zha.PROFILE_ID,
        SIG_EP_TYPE: zha.DeviceType.THERMOSTAT,
        SIG_EP_INPUT: [
            zigpy.zcl.clusters.general.Basic.cluster_id,
            zigpy.zcl.clusters.general.Identify.cluster_id,
            zigpy.zcl.clusters.hvac.Thermostat.cluster_id,
            zigpy.zcl.clusters.hvac.UserInterface.cluster_id,
        ],
        SIG_EP_OUTPUT: [zigpy.zcl.clusters.general.Ota.cluster_id],
    }
}

CLIMATE_FAN = {
    1: {
        SIG_EP_PROFILE: zha.PROFILE_ID,
        SIG_EP_TYPE: zha.DeviceType.THERMOSTAT,
        SIG_EP_INPUT: [
            zigpy.zcl.clusters.general.Basic.cluster_id,
            zigpy.zcl.clusters.general.Identify.cluster_id,
            zigpy.zcl.clusters.hvac.Fan.cluster_id,
            zigpy.zcl.clusters.hvac.Thermostat.cluster_id,
            zigpy.zcl.clusters.hvac.UserInterface.cluster_id,
        ],
        SIG_EP_OUTPUT: [zigpy.zcl.clusters.general.Ota.cluster_id],
    }
}

CLIMATE_SINOPE = {
    1: {
        SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
        SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.THERMOSTAT,
        SIG_EP_INPUT: [
            zigpy.zcl.clusters.general.Basic.cluster_id,
            zigpy.zcl.clusters.general.Identify.cluster_id,
            zigpy.zcl.clusters.hvac.Thermostat.cluster_id,
            zigpy.zcl.clusters.hvac.UserInterface.cluster_id,
            65281,
        ],
        SIG_EP_OUTPUT: [zigpy.zcl.clusters.general.Ota.cluster_id, 65281],
    },
    196: {
        SIG_EP_PROFILE: 0xC25D,
        SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.THERMOSTAT,
        SIG_EP_INPUT: [zigpy.zcl.clusters.general.PowerConfiguration.cluster_id],
        SIG_EP_OUTPUT: [],
    },
}

MANUF_SINOPE = "Sinope Technologies"

ZCL_ATTR_PLUG = {
    "abs_min_heat_setpoint_limit": 800,
    "abs_max_heat_setpoint_limit": 3000,
    "abs_min_cool_setpoint_limit": 2000,
    "abs_max_cool_setpoint_limit": 4000,
    "ctrl_sequence_of_oper": Thermostat.ControlSequenceOfOperation.Cooling_and_Heating,
    "local_temperature": None,
    "max_cool_setpoint_limit": 3900,
    "max_heat_setpoint_limit": 2900,
    "min_cool_setpoint_limit": 2100,
    "min_heat_setpoint_limit": 700,
    "occupancy": 1,
    "occupied_cooling_setpoint": 2500,
    "occupied_heating_setpoint": 2200,
    "pi_cooling_demand": None,
    "pi_heating_demand": None,
    "running_mode": Thermostat.RunningMode.Off,
    "running_state": None,
    "system_mode": Thermostat.SystemMode.Off,
    "unoccupied_heating_setpoint": 2200,
    "unoccupied_cooling_setpoint": 2300,
}


@pytest.fixture(autouse=True)
def climate_platform_only():
    """Only set up the climate and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BUTTON,
            Platform.CLIMATE,
            Platform.BINARY_SENSOR,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
        ),
    ):
        yield


@pytest.fixture
def device_climate_mock(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., ZigbeeDevice],
):
    """Test regular thermostat device."""

    async def _dev(clusters, plug=None, manuf=None, quirk=None):
        plugged_attrs = ZCL_ATTR_PLUG if plug is None else {**ZCL_ATTR_PLUG, **plug}
        zigpy_device = zigpy_device_mock(clusters, manufacturer=manuf, quirk=quirk)
        zigpy_device.node_desc.mac_capability_flags |= 0b_0000_0100
        zigpy_device.endpoints[1].thermostat.PLUGGED_ATTR_READS = plugged_attrs

        await setup_zha()
        gateway = get_zha_gateway(hass)
        gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)
        gateway.get_or_create_device(zigpy_device)
        await gateway.async_device_initialized(zigpy_device)
        await hass.async_block_till_done(wait_background_tasks=True)
        return gateway_proxy.get_device_proxy(zigpy_device.ieee)

    return _dev


@pytest.fixture
async def device_climate(device_climate_mock):
    """Plain Climate device."""

    return await device_climate_mock(CLIMATE)


@pytest.fixture
async def device_climate_fan(device_climate_mock):
    """Test thermostat with fan device."""

    return await device_climate_mock(CLIMATE_FAN)


@pytest.fixture
@patch.object(
    zigpy.zcl.clusters.manufacturer_specific.ManufacturerSpecificCluster,
    "ep_attribute",
    "sinope_manufacturer_specific",
)
async def device_climate_sinope(device_climate_mock):
    """Sinope thermostat."""

    return await device_climate_mock(
        CLIMATE_SINOPE,
        manuf=MANUF_SINOPE,
        quirk=zhaquirks.sinope.thermostat.SinopeTechnologiesThermostat,
    )


def test_sequence_mappings() -> None:
    """Test correct mapping between control sequence -> HVAC Mode -> Sysmode."""

    for hvac_modes in SEQ_OF_OPERATION.values():
        for hvac_mode in hvac_modes:
            assert hvac_mode in HVAC_MODE_2_SYSTEM
            assert Thermostat.SystemMode(HVAC_MODE_2_SYSTEM[hvac_mode]) is not None


async def test_climate_local_temperature(hass: HomeAssistant, device_climate) -> None:
    """Test local temperature."""

    thrm_cluster = device_climate.device.device.endpoints[1].thermostat
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None

    await send_attributes_report(hass, thrm_cluster, {0: 2100})
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.0


async def test_climate_hvac_action_running_state(
    hass: HomeAssistant, device_climate_sinope
) -> None:
    """Test hvac action via running state."""

    thrm_cluster = device_climate_sinope.device.device.endpoints[1].thermostat
    entity_id = find_entity_id(Platform.CLIMATE, device_climate_sinope, hass)
    sensor_entity_id = find_entity_id(
        Platform.SENSOR, device_climate_sinope, hass, "hvac"
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    hvac_sensor_state = hass.states.get(sensor_entity_id)
    assert hvac_sensor_state.state == HVACAction.OFF

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Off}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    hvac_sensor_state = hass.states.get(sensor_entity_id)
    assert hvac_sensor_state.state == HVACAction.OFF

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Auto}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    hvac_sensor_state = hass.states.get(sensor_entity_id)
    assert hvac_sensor_state.state == HVACAction.IDLE

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Cool}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING
    hvac_sensor_state = hass.states.get(sensor_entity_id)
    assert hvac_sensor_state.state == HVACAction.COOLING

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Heat}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    hvac_sensor_state = hass.states.get(sensor_entity_id)
    assert hvac_sensor_state.state == HVACAction.HEATING

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Off}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    hvac_sensor_state = hass.states.get(sensor_entity_id)
    assert hvac_sensor_state.state == HVACAction.IDLE

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Fan_State_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.FAN
    hvac_sensor_state = hass.states.get(sensor_entity_id)
    assert hvac_sensor_state.state == HVACAction.FAN


async def test_climate_hvac_action_pi_demand(
    hass: HomeAssistant, device_climate
) -> None:
    """Test hvac action based on pi_heating/cooling_demand attrs."""

    thrm_cluster = device_climate.device.device.endpoints[1].thermostat
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)

    state = hass.states.get(entity_id)
    assert ATTR_HVAC_ACTION not in state.attributes

    await send_attributes_report(hass, thrm_cluster, {0x0007: 10})
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING

    await send_attributes_report(hass, thrm_cluster, {0x0008: 20})
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING

    await send_attributes_report(hass, thrm_cluster, {0x0007: 0})
    await send_attributes_report(hass, thrm_cluster, {0x0008: 0})

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Heat}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Cool}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


@pytest.mark.parametrize(
    ("sys_mode", "hvac_mode"),
    [
        (Thermostat.SystemMode.Auto, HVACMode.HEAT_COOL),
        (Thermostat.SystemMode.Cool, HVACMode.COOL),
        (Thermostat.SystemMode.Heat, HVACMode.HEAT),
        (Thermostat.SystemMode.Pre_cooling, HVACMode.COOL),
        (Thermostat.SystemMode.Fan_only, HVACMode.FAN_ONLY),
        (Thermostat.SystemMode.Dry, HVACMode.DRY),
    ],
)
async def test_hvac_mode(
    hass: HomeAssistant, device_climate, sys_mode, hvac_mode
) -> None:
    """Test HVAC mode."""

    thrm_cluster = device_climate.device.device.endpoints[1].thermostat
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    await send_attributes_report(hass, thrm_cluster, {0x001C: sys_mode})
    state = hass.states.get(entity_id)
    assert state.state == hvac_mode

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Off}
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    await send_attributes_report(hass, thrm_cluster, {0x001C: 0xFF})
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("seq_of_op", "modes"),
    [
        (0xFF, {HVACMode.OFF}),
        (0x00, {HVACMode.OFF, HVACMode.COOL}),
        (0x01, {HVACMode.OFF, HVACMode.COOL}),
        (0x02, {HVACMode.OFF, HVACMode.HEAT}),
        (0x03, {HVACMode.OFF, HVACMode.HEAT}),
        (0x04, {HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL}),
        (0x05, {HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL}),
    ],
)
async def test_hvac_modes(
    hass: HomeAssistant, device_climate_mock, seq_of_op, modes
) -> None:
    """Test HVAC modes from sequence of operations."""

    device_climate = await device_climate_mock(
        CLIMATE, {"ctrl_sequence_of_oper": seq_of_op}
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    state = hass.states.get(entity_id)
    assert set(state.attributes[ATTR_HVAC_MODES]) == modes


@pytest.mark.parametrize(
    ("sys_mode", "preset", "target_temp"),
    [
        (Thermostat.SystemMode.Heat, None, 22),
        (Thermostat.SystemMode.Heat, PRESET_AWAY, 16),
        (Thermostat.SystemMode.Cool, None, 25),
        (Thermostat.SystemMode.Cool, PRESET_AWAY, 27),
    ],
)
async def test_target_temperature(
    hass: HomeAssistant,
    device_climate_mock,
    sys_mode: Thermostat.SystemMode,
    preset: Literal[PRESET_AWAY] | None,
    target_temp: int,
) -> None:
    """Test target temperature property."""

    device_climate = await device_climate_mock(
        CLIMATE_SINOPE,
        {
            "occupied_cooling_setpoint": 2500,
            "occupied_heating_setpoint": 2200,
            "system_mode": sys_mode,
            "unoccupied_heating_setpoint": 1600,
            "unoccupied_cooling_setpoint": 2700,
        },
        manuf=MANUF_SINOPE,
        quirk=zhaquirks.sinope.thermostat.SinopeTechnologiesThermostat,
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    if preset:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == target_temp


@pytest.mark.parametrize(
    ("preset", "unoccupied", "target_temp"),
    [
        (None, 1800, 17),
        (PRESET_AWAY, 1800, 18),
        (PRESET_AWAY, None, None),
    ],
)
async def test_target_temperature_high(
    hass: HomeAssistant, device_climate_mock, preset, unoccupied, target_temp
) -> None:
    """Test target temperature high property."""

    device_climate = await device_climate_mock(
        CLIMATE_SINOPE,
        {
            "occupied_cooling_setpoint": 1700,
            "system_mode": Thermostat.SystemMode.Auto,
            "unoccupied_cooling_setpoint": unoccupied,
        },
        manuf=MANUF_SINOPE,
        quirk=zhaquirks.sinope.thermostat.SinopeTechnologiesThermostat,
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    if preset:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == target_temp


@pytest.mark.parametrize(
    ("preset", "unoccupied", "target_temp"),
    [
        (None, 1600, 21),
        (PRESET_AWAY, 1600, 16),
        (PRESET_AWAY, None, None),
    ],
)
async def test_target_temperature_low(
    hass: HomeAssistant, device_climate_mock, preset, unoccupied, target_temp
) -> None:
    """Test target temperature low property."""

    device_climate = await device_climate_mock(
        CLIMATE_SINOPE,
        {
            "occupied_heating_setpoint": 2100,
            "system_mode": Thermostat.SystemMode.Auto,
            "unoccupied_heating_setpoint": unoccupied,
        },
        manuf=MANUF_SINOPE,
        quirk=zhaquirks.sinope.thermostat.SinopeTechnologiesThermostat,
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    if preset:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == target_temp


@pytest.mark.parametrize(
    ("hvac_mode", "sys_mode"),
    [
        (HVACMode.AUTO, None),
        (HVACMode.COOL, Thermostat.SystemMode.Cool),
        (HVACMode.DRY, None),
        (HVACMode.FAN_ONLY, None),
        (HVACMode.HEAT, Thermostat.SystemMode.Heat),
        (HVACMode.HEAT_COOL, Thermostat.SystemMode.Auto),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant, device_climate, hvac_mode, sys_mode
) -> None:
    """Test setting hvac mode."""

    thrm_cluster = device_climate.device.device.endpoints[1].thermostat
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    if sys_mode is not None:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == hvac_mode
        assert thrm_cluster.write_attributes.call_count == 1
        assert thrm_cluster.write_attributes.call_args[0][0] == {
            "system_mode": sys_mode
        }
    else:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_HVAC_MODE,
                {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
                blocking=True,
            )
        state = hass.states.get(entity_id)
        assert thrm_cluster.write_attributes.call_count == 0
        assert state.state == HVACMode.OFF

    # turn off
    thrm_cluster.write_attributes.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF
    assert thrm_cluster.write_attributes.call_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {
        "system_mode": Thermostat.SystemMode.Off
    }


async def test_set_temperature_hvac_mode(hass: HomeAssistant, device_climate) -> None:
    """Test setting HVAC mode in temperature service call."""

    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    thrm_cluster = device_climate.device.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            ATTR_TEMPERATURE: 20,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT_COOL
    assert thrm_cluster.write_attributes.await_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {
        "system_mode": Thermostat.SystemMode.Auto
    }


async def test_set_temperature_heat_cool(
    hass: HomeAssistant, device_climate_mock
) -> None:
    """Test setting temperature service call in heating/cooling HVAC mode."""

    device_climate = await device_climate_mock(
        CLIMATE_SINOPE,
        {
            "occupied_cooling_setpoint": 2500,
            "occupied_heating_setpoint": 2000,
            "system_mode": Thermostat.SystemMode.Auto,
            "unoccupied_heating_setpoint": 1600,
            "unoccupied_cooling_setpoint": 2700,
        },
        manuf=MANUF_SINOPE,
        quirk=zhaquirks.sinope.thermostat.SinopeTechnologiesThermostat,
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    thrm_cluster = device_climate.device.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT_COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 20.0
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 25.0
    assert thrm_cluster.write_attributes.await_count == 0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_HIGH: 26,
            ATTR_TARGET_TEMP_LOW: 19,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 19.0
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 26.0
    assert thrm_cluster.write_attributes.await_count == 2
    assert thrm_cluster.write_attributes.call_args_list[0][0][0] == {
        "occupied_heating_setpoint": 1900
    }
    assert thrm_cluster.write_attributes.call_args_list[1][0][0] == {
        "occupied_cooling_setpoint": 2600
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    thrm_cluster.write_attributes.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_HIGH: 30,
            ATTR_TARGET_TEMP_LOW: 15,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 15.0
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 30.0
    assert thrm_cluster.write_attributes.await_count == 2
    assert thrm_cluster.write_attributes.call_args_list[0][0][0] == {
        "unoccupied_heating_setpoint": 1500
    }
    assert thrm_cluster.write_attributes.call_args_list[1][0][0] == {
        "unoccupied_cooling_setpoint": 3000
    }


async def test_set_temperature_heat(hass: HomeAssistant, device_climate_mock) -> None:
    """Test setting temperature service call in heating HVAC mode."""

    device_climate = await device_climate_mock(
        CLIMATE_SINOPE,
        {
            "occupied_cooling_setpoint": 2500,
            "occupied_heating_setpoint": 2000,
            "system_mode": Thermostat.SystemMode.Heat,
            "unoccupied_heating_setpoint": 1600,
            "unoccupied_cooling_setpoint": 2700,
        },
        manuf=MANUF_SINOPE,
        quirk=zhaquirks.sinope.thermostat.SinopeTechnologiesThermostat,
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    thrm_cluster = device_climate.device.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_HIGH: 30,
            ATTR_TARGET_TEMP_LOW: 15,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] == 20.0
    assert thrm_cluster.write_attributes.await_count == 0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] == 21.0
    assert thrm_cluster.write_attributes.await_count == 1
    assert thrm_cluster.write_attributes.call_args_list[0][0][0] == {
        "occupied_heating_setpoint": 2100
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    thrm_cluster.write_attributes.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert thrm_cluster.write_attributes.await_count == 1
    assert thrm_cluster.write_attributes.call_args_list[0][0][0] == {
        "unoccupied_heating_setpoint": 2200
    }


async def test_set_temperature_cool(hass: HomeAssistant, device_climate_mock) -> None:
    """Test setting temperature service call in cooling HVAC mode."""

    device_climate = await device_climate_mock(
        CLIMATE_SINOPE,
        {
            "occupied_cooling_setpoint": 2500,
            "occupied_heating_setpoint": 2000,
            "system_mode": Thermostat.SystemMode.Cool,
            "unoccupied_cooling_setpoint": 1600,
            "unoccupied_heating_setpoint": 2700,
        },
        manuf=MANUF_SINOPE,
        quirk=zhaquirks.sinope.thermostat.SinopeTechnologiesThermostat,
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    thrm_cluster = device_climate.device.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.COOL

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_HIGH: 30,
            ATTR_TARGET_TEMP_LOW: 15,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] == 25.0
    assert thrm_cluster.write_attributes.await_count == 0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] == 21.0
    assert thrm_cluster.write_attributes.await_count == 1
    assert thrm_cluster.write_attributes.call_args_list[0][0][0] == {
        "occupied_cooling_setpoint": 2100
    }

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    thrm_cluster.write_attributes.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert thrm_cluster.write_attributes.await_count == 1
    assert thrm_cluster.write_attributes.call_args_list[0][0][0] == {
        "unoccupied_cooling_setpoint": 2200
    }


async def test_set_temperature_wrong_mode(
    hass: HomeAssistant, device_climate_mock
) -> None:
    """Test setting temperature service call for wrong HVAC mode."""

    with patch.object(
        zigpy.zcl.clusters.manufacturer_specific.ManufacturerSpecificCluster,
        "ep_attribute",
        "sinope_manufacturer_specific",
    ):
        device_climate = await device_climate_mock(
            CLIMATE_SINOPE,
            {
                "occupied_cooling_setpoint": 2500,
                "occupied_heating_setpoint": 2000,
                "system_mode": Thermostat.SystemMode.Dry,
                "unoccupied_cooling_setpoint": 1600,
                "unoccupied_heating_setpoint": 2700,
            },
            manuf=MANUF_SINOPE,
        )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    thrm_cluster = device_climate.device.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.DRY

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 24},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert thrm_cluster.write_attributes.await_count == 0


async def test_fan_mode(hass: HomeAssistant, device_climate_fan) -> None:
    """Test fan mode."""

    entity_id = find_entity_id(Platform.CLIMATE, device_climate_fan, hass)
    thrm_cluster = device_climate_fan.device.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert set(state.attributes[ATTR_FAN_MODES]) == {FAN_AUTO, FAN_ON}
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO

    await send_attributes_report(
        hass, thrm_cluster, {"running_state": Thermostat.RunningState.Fan_State_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_FAN_MODE] == FAN_ON

    await send_attributes_report(
        hass, thrm_cluster, {"running_state": Thermostat.RunningState.Idle}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO

    await send_attributes_report(
        hass, thrm_cluster, {"running_state": Thermostat.RunningState.Fan_2nd_Stage_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_FAN_MODE] == FAN_ON


async def test_set_fan_mode_not_supported(
    hass: HomeAssistant, device_climate_fan
) -> None:
    """Test fan setting unsupported mode."""

    entity_id = find_entity_id(Platform.CLIMATE, device_climate_fan, hass)
    fan_cluster = device_climate_fan.device.device.endpoints[1].fan

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_LOW},
            blocking=True,
        )
    assert fan_cluster.write_attributes.await_count == 0


async def test_set_fan_mode(hass: HomeAssistant, device_climate_fan) -> None:
    """Test fan mode setting."""

    entity_id = find_entity_id(Platform.CLIMATE, device_climate_fan, hass)
    fan_cluster = device_climate_fan.device.device.endpoints[1].fan

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_ON},
        blocking=True,
    )
    assert fan_cluster.write_attributes.await_count == 1
    assert fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 4}

    fan_cluster.write_attributes.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_AUTO},
        blocking=True,
    )
    assert fan_cluster.write_attributes.await_count == 1
    assert fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 5}


def _enable_weekly_schedule(device_climate) -> None:
    """Expose the standard ZCL schedule feature on the mocked thermostat."""
    device_climate.device.exposes_features.add(THERMOSTAT_WEEKLY_SCHEDULE)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ("temperature=23", "YAML mapping"),
        ({"temperatur": 23}, "Add `temperature: 23`"),
        ({"temperature": "23"}, "must be a number in °C"),
    ],
)
def test_weekly_schedule_conversion_errors_explain_temperature_format(
    data: object, message: str
) -> None:
    """Malformed block data explains the expected key and YAML mapping."""
    schedule = {day: [] for day in WEEKDAY_TO_CONF.values()}
    schedule["monday"] = [
        {
            "from": time(6),
            "to": time(22),
            "data": data,
        }
    ]

    with pytest.raises(ScheduleConversionError, match=message):
        schedule_to_transitions(schedule, gap_temperature=17)


@pytest.mark.parametrize(
    "times",
    [
        [],
        [(time(6), time.max)],
        [(time.min, time(18))],
        [(time.min, time(6)), (time(18), time.max)],
    ],
)
def test_weekly_schedule_coverage_error_explains_both_fixes(
    times: list[tuple[time, time]],
) -> None:
    """Empty days and gaps explain the fallback and full-day alternatives."""
    schedule = {
        day: [{"from": time.min, "to": time.max, "data": {"temperature": 21}}]
        for day in WEEKDAY_TO_CONF.values()
    }
    schedule["monday"] = [
        {"from": start, "to": stop, "data": {"temperature": 21}}
        for start, stop in times
    ]

    with pytest.raises(ScheduleConversionError) as err:
        schedule_to_transitions(schedule)
    assert str(err.value) == (
        "The Monday schedule has times without a temperature. "
        "Set a default temperature outside of time blocks when linking "
        "the helper, or add time blocks covering the whole day from 00:00 to 24:00."
    )

    # Either suggested fix makes this schedule convertible.
    assert schedule_to_transitions(schedule, gap_temperature=17)["monday"]
    schedule["monday"] = [
        {"from": time.min, "to": time.max, "data": {"temperature": 21}}
    ]
    assert schedule_to_transitions(schedule)["monday"] == [(0, 2100)]


async def test_weekly_schedule_helper_round_trip(
    hass: HomeAssistant, device_climate
) -> None:
    """Upload a real helper and read the mocked thermostat through HA actions."""
    _enable_weekly_schedule(device_climate)
    days = {
        day: [
            {"from": "00:00", "to": "08:00", "data": {"temperature": 19.5}},
            {"from": "08:00", "to": "24:00", "data": {"temperature": 21.25}},
        ]
        for day in WEEKDAY_TO_CONF.values()
    }
    assert await async_setup_component(
        hass, "schedule", {"schedule": {"heating": {"name": "Heating", **days}}}
    )
    await hass.async_block_till_done()
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    cluster = device_climate.device.device.endpoints[1].thermostat
    stored = {bit: [] for bit in (1, 2, 4, 8, 16, 32, 64)}

    async def command(command_id, **kwargs):
        if command_id == 2:
            day = int(kwargs["days_to_return"])
            values = stored[day]
            return Thermostat.ClientCommandDefs.get_weekly_schedule_response.schema(
                num_transitions_for_sequence=len(values) // 2,
                day_of_week_for_sequence=day,
                mode_for_sequence=1,
                values=values,
            )
        if command_id == 1:
            stored[int(kwargs["day_of_week_for_sequence"])] = list(kwargs["values"])
        elif command_id == 3:
            for day in stored:
                stored[day] = []
        else:
            raise AssertionError(f"Unexpected command {command_id}")
        return DefaultResponse(command_id=command_id, status=Status.SUCCESS)

    cluster.command = AsyncMock(side_effect=command)
    response = await hass.services.async_call(
        ZHA_DOMAIN,
        ZHAService.SET_WEEKLY_SCHEDULE,
        {"entity_id": entity_id, "schedule_entity": "schedule.heating"},
        blocking=True,
        return_response=True,
    )
    result = response[entity_id]
    assert result["complete"]
    assert result["pre_write_snapshot"]["complete"]
    assert result["pre_write_snapshot"]["days"]["monday"]["transitions"] == []
    assert result["days"]["monday"]["transitions"] == [
        {"time": "00:00", "temperature": 19.5},
        {"time": "08:00", "temperature": 21.25},
    ]
    assert all(values == [0, 1950, 480, 2125] for values in stored.values())
    json.dumps(response, allow_nan=False)

    cluster.command.reset_mock()
    cached = await hass.services.async_call(
        ZHA_DOMAIN,
        ZHAService.GET_WEEKLY_SCHEDULE,
        {"entity_id": entity_id, "cache_only": True},
        blocking=True,
        return_response=True,
    )
    assert cached[entity_id] == result
    cluster.command.assert_not_awaited()

    fresh = await hass.services.async_call(
        ZHA_DOMAIN,
        ZHAService.GET_WEEKLY_SCHEDULE,
        {"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )
    assert fresh[entity_id]["complete"]
    assert cluster.command.await_count == 7

    cluster.command.reset_mock()
    cleared = await hass.services.async_call(
        ZHA_DOMAIN,
        ZHAService.CLEAR_WEEKLY_SCHEDULE,
        {"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )
    assert cleared[entity_id]["complete"]
    assert all(day["transitions"] == [] for day in cleared[entity_id]["days"].values())
    assert (
        cleared[entity_id]["pre_write_snapshot"]["days"]["monday"]["transitions"]
        == result["days"]["monday"]["transitions"]
    )
    assert all(values == [] for values in stored.values())
    assert [item.args[0] for item in cluster.command.await_args_list] == (
        [2] * 7 + [3] + [2] * 7
    )
    json.dumps(cleared, allow_nan=False)

    assert (
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.CLEAR_WEEKLY_SCHEDULE,
            {"entity_id": entity_id},
            blocking=True,
        )
        is None
    )


async def test_weekly_schedule_entity_and_helper_permissions(
    hass: HomeAssistant, device_climate, hass_read_only_user: MockUser
) -> None:
    """Climate and schedule-helper permissions are both enforced for non-admins."""
    _enable_weekly_schedule(device_climate)
    days = {
        day: [{"from": "00:00", "to": "24:00", "data": {"temperature": 20}}]
        for day in WEEKDAY_TO_CONF.values()
    }
    assert await async_setup_component(
        hass, "schedule", {"schedule": {"heating": {"name": "Heating", **days}}}
    )
    await hass.async_block_till_done()
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    context = Context(user_id=hass_read_only_user.id)
    cluster = device_climate.device.device.endpoints[1].thermostat
    cluster.command = AsyncMock()

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.GET_WEEKLY_SCHEDULE,
            {"entity_id": entity_id, "cache_only": True},
            context=context,
            blocking=True,
            return_response=True,
        )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.CLEAR_WEEKLY_SCHEDULE,
            {"entity_id": entity_id},
            context=context,
            blocking=True,
        )

    hass_read_only_user.mock_policy({"entities": {"entity_ids": {entity_id: True}}})
    result = await hass.services.async_call(
        ZHA_DOMAIN,
        ZHAService.GET_WEEKLY_SCHEDULE,
        {"entity_id": entity_id, "cache_only": True},
        context=context,
        blocking=True,
        return_response=True,
    )
    assert not result[entity_id]["complete"]

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.SET_WEEKLY_SCHEDULE,
            {"entity_id": entity_id, "schedule_entity": "schedule.heating"},
            context=context,
            blocking=True,
        )
    cluster.command.assert_not_awaited()


async def test_weekly_schedule_requires_exposed_feature(
    hass: HomeAssistant, device_climate
) -> None:
    """Thermostats without a schedule provider fail explicitly."""
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.GET_WEEKLY_SCHEDULE,
            {"entity_id": entity_id, "cache_only": True},
            blocking=True,
            return_response=True,
        )
    assert err.value.translation_key == "weekly_schedule_unsupported"


async def test_weekly_schedule_clear_unsupported_by_provider(
    hass: HomeAssistant, device_climate
) -> None:
    """A provider without clear support does not disable schedule reads."""
    _enable_weekly_schedule(device_climate)
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    zha_entity = device_climate.device.get_entity(Platform.CLIMATE, pick_first=True)
    provider = zha_entity.weekly_schedule
    with patch.object(
        provider, "capabilities", WeeklyScheduleCapabilities(supports_clear=False)
    ):
        result = await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.GET_WEEKLY_SCHEDULE,
            {"entity_id": entity_id, "cache_only": True},
            blocking=True,
            return_response=True,
        )
        assert not result[entity_id]["complete"]
        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                ZHA_DOMAIN,
                ZHAService.CLEAR_WEEKLY_SCHEDULE,
                {"entity_id": entity_id},
                blocking=True,
            )
    assert err.value.translation_key == "weekly_schedule_clear_unsupported"


async def test_weekly_schedule_clear_surfaces_library_failure(
    hass: HomeAssistant, device_climate
) -> None:
    """A failed clear is reported to the action caller."""
    _enable_weekly_schedule(device_climate)
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    zha_entity = device_climate.device.get_entity(Platform.CLIMATE, pick_first=True)
    with (
        patch.object(
            zha_entity.weekly_schedule,
            "async_clear",
            side_effect=ZHAException("Schedule clear could not be verified"),
        ),
        pytest.raises(HomeAssistantError, match="Schedule clear could not be verified"),
    ):
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.CLEAR_WEEKLY_SCHEDULE,
            {"entity_id": entity_id},
            blocking=True,
        )


def _fake_schedule_device(device_climate) -> tuple[dict[int, list[int]], AsyncMock]:
    """Store weekly schedule writes of the mocked thermostat in memory."""
    cluster = device_climate.device.device.endpoints[1].thermostat
    stored: dict[int, list[int]] = {bit: [] for bit in (1, 2, 4, 8, 16, 32, 64)}

    async def command(command_id, **kwargs):
        if command_id == 2:
            day = int(kwargs["days_to_return"])
            return Thermostat.ClientCommandDefs.get_weekly_schedule_response.schema(
                num_transitions_for_sequence=len(stored[day]) // 2,
                day_of_week_for_sequence=day,
                mode_for_sequence=1,
                values=stored[day],
            )
        if command_id == 1:
            stored[int(kwargs["day_of_week_for_sequence"])] = list(kwargs["values"])
        if command_id == 3:
            for values in stored.values():
                values.clear()
        return DefaultResponse(command_id=command_id, status=Status.SUCCESS)

    cluster.command = AsyncMock(side_effect=command)
    return stored, cluster.command


async def _flush_sync(hass: HomeAssistant, delay: timedelta) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + delay)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _write_heating_helper(client, temperature: int, *, create: bool) -> None:
    payload = {
        "type": "schedule/create" if create else "schedule/update",
        "name": "Heating",
        "monday": [
            {
                "from": "06:00:00",
                "to": "22:00:00",
                "data": {"temperature": temperature},
            }
        ],
    }
    if not create:
        payload["schedule_id"] = "heating"
    await client.send_json_auto_id(payload)
    assert (await client.receive_json())["success"]


async def test_weekly_schedule_link_lifecycle(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_climate,
) -> None:
    """A created helper is linked, synced on edits, and unlinked over WebSocket."""
    _enable_weekly_schedule(device_climate)
    stored, command = _fake_schedule_device(device_climate)
    assert await async_setup_component(hass, "schedule", {})
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    client = await hass_ws_client(hass)
    day = [{"from": "06:00:00", "to": "22:00:00", "data": {"temperature": 21}}]

    await client.send_json_auto_id(
        {"type": "schedule/create", "name": "Heating", "monday": day}
    )
    assert (await client.receive_json())["success"]

    await client.send_json_auto_id({"type": "zha/weekly_schedules/list"})
    listed = (await client.receive_json())["result"]
    assert [item["entity_id"] for item in listed["thermostats"]] == [entity_id]
    assert listed["links"] == []

    await client.send_json_auto_id({"type": "zha/weekly_schedules/subscribe"})
    sub_id = (await client.receive_json())["id"]
    assert (await client.receive_json())["event"]["links"] == []

    await client.send_json_auto_id(
        {
            "type": "zha/weekly_schedules/add",
            "thermostat_entity_id": entity_id,
            "schedule_entity_id": "schedule.heating",
            "gap_temperature": 17,
        }
    )
    messages = {
        message["type"]: message
        for message in (await client.receive_json(), await client.receive_json())
    }
    added = messages["result"]
    link_id = added["result"]["link_id"]
    assert added["result"]["state"] == "pending"
    assert messages["event"]["id"] == sub_id
    assert messages["event"]["event"]["links"][0]["link_id"] == link_id
    await client.send_json_auto_id(
        {"type": "unsubscribe_events", "subscription": sub_id}
    )
    assert (await client.receive_json())["success"]
    entry = hass.config_entries.async_entries(ZHA_DOMAIN)[0]
    assert [link["link_id"] for link in entry.options[CONF_WEEKLY_SCHEDULE_LINKS]] == [
        link_id
    ]

    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert stored[2] == [0, 1700, 360, 2100, 1320, 1700]
    assert all(stored[bit] == [0, 1700] for bit in (1, 4, 8, 16, 32, 64))
    status = get_zha_data(hass).weekly_schedule_sync.async_links()[0]
    assert status["state"] == "synced"
    assert len(status["written_days"]) == 7

    # Editing only Monday writes only Monday.
    command.reset_mock()
    await client.send_json_auto_id(
        {
            "type": "schedule/update",
            "schedule_id": "heating",
            "name": "Heating",
            "monday": [{**day[0], "data": {"temperature": 20}}],
        }
    )
    assert (await client.receive_json())["success"]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert stored[2] == [0, 1700, 360, 2000, 1320, 1700]
    writes = [call for call in command.call_args_list if call.args[0] == 1]
    assert [int(call.kwargs["day_of_week_for_sequence"]) for call in writes] == [2]
    status = get_zha_data(hass).weekly_schedule_sync.async_links()[0]
    assert status["written_days"] == ["monday"]

    command.reset_mock()
    await client.send_json_auto_id(
        {"type": "zha/weekly_schedules/sync", "link_id": link_id}
    )
    assert (await client.receive_json())["success"]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert len([call for call in command.call_args_list if call.args[0] == 2]) == 7
    assert not [call for call in command.call_args_list if call.args[0] == 1]

    # Recreate link state from persisted options, as on startup.
    manager = get_zha_data(hass).weekly_schedule_sync
    manager.async_shutdown()
    manager.async_start()
    assert manager.async_links()[0]["link_id"] == link_id
    command.reset_mock()
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "synced"
    assert len([call for call in command.call_args_list if call.args[0] == 2]) == 7
    assert not [call for call in command.call_args_list if call.args[0] == 1]

    # Editing the link keeps its ID and thermostat and resyncs the new defaults.
    command.reset_mock()
    await client.send_json_auto_id(
        {
            "type": "zha/weekly_schedules/update",
            "link_id": link_id,
            "schedule_entity_id": "schedule.heating",
            "gap_temperature": 16,
        }
    )
    updated = (await client.receive_json())["result"]
    assert updated["link_id"] == link_id
    assert updated["thermostat_entity_id"] == entity_id
    assert updated["gap_temperature"] == 16
    assert entry.options[CONF_WEEKLY_SCHEDULE_LINKS][0]["gap_temperature"] == 16
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert stored[2] == [0, 1600, 360, 2000, 1320, 1600]
    assert all(stored[bit] == [0, 1600] for bit in (1, 4, 8, 16, 32, 64))
    assert len(manager.async_links()) == 1

    await client.send_json_auto_id(
        {
            "type": "zha/weekly_schedules/update",
            "link_id": "unknown",
            "schedule_entity_id": "schedule.heating",
        }
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"

    await client.send_json_auto_id(
        {"type": "zha/weekly_schedules/remove", "link_id": link_id}
    )
    assert (await client.receive_json())["success"]
    assert CONF_WEEKLY_SCHEDULE_LINKS not in entry.options
    # Removing a link clears the thermostat's schedule.
    assert all(values == [] for values in stored.values())

    await client.send_json_auto_id(
        {"type": "zha/weekly_schedules/sync", "link_id": link_id}
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"


async def test_weekly_schedule_edit_during_slow_upload(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_climate,
) -> None:
    """A helper edit during an upload longer than the cooldown is synced."""
    _enable_weekly_schedule(device_climate)
    stored, _ = _fake_schedule_device(device_climate)
    assert await async_setup_component(hass, "schedule", {})
    client = await hass_ws_client(hass)
    await _write_heating_helper(client, 18, create=True)
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    provider = device_climate.device.get_entity(
        Platform.CLIMATE, pick_first=True
    ).weekly_schedule
    set_schedule = provider.async_set
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_set(schedule, *, only_changed=False):
        if not started.is_set():
            started.set()
            await release.wait()
        return await set_schedule(schedule, only_changed=only_changed)

    with patch.object(provider, "async_set", side_effect=slow_set) as set_mock:
        manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
        await asyncio.wait_for(started.wait(), 2)
        await _write_heating_helper(client, 22, create=False)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
        await hass.async_block_till_done()
        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))

    assert set_mock.await_count == 2
    assert stored[2] == [0, 1700, 360, 2200, 1320, 1700]
    assert manager.async_links()[0]["state"] == "synced"


async def test_weekly_schedule_update_waits_for_old_sync(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    device_climate,
) -> None:
    """A replacement starts only after the old upload can no longer write."""
    _enable_weekly_schedule(device_climate)
    _, command = _fake_schedule_device(device_climate)
    assert await async_setup_component(
        hass,
        "schedule",
        {
            "schedule": {
                "heating": {
                    "name": "Heating",
                    "monday": [{"from": "06:00:00", "to": "22:00:00"}],
                }
            }
        },
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    provider = device_climate.device.get_entity(
        Platform.CLIMATE, pick_first=True
    ).weekly_schedule
    set_schedule = provider.async_set
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_set(schedule, *, only_changed=False):
        started.set()
        await release.wait()
        return await set_schedule(schedule, only_changed=only_changed)

    with patch.object(provider, "async_set", side_effect=slow_set):
        link_id = manager.async_add_link(
            entity_id, "schedule.heating", block_temperature=18, gap_temperature=17
        )["link_id"]
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
        await asyncio.wait_for(started.wait(), 2)
        update = asyncio.create_task(
            manager.async_update_link(link_id, "schedule.heating", block_temperature=18)
        )
        await asyncio.sleep(0)
        assert not update.done()
        release.set()
        await update
        command_count = command.call_count
        await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))

    assert manager.async_links()[0]["state"] == "error"
    assert issue_registry.async_get_issue(ZHA_DOMAIN, f"{ISSUE_SYNC_FAILED}_{link_id}")
    assert command.call_count == command_count


async def test_weekly_schedule_remove_rejects_concurrent_changes(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_climate,
) -> None:
    """Removing a link cannot race an edit, sync or second removal."""
    _enable_weekly_schedule(device_climate)
    stored, _ = _fake_schedule_device(device_climate)
    assert await async_setup_component(hass, "schedule", {})
    client = await hass_ws_client(hass)
    await _write_heating_helper(client, 18, create=True)
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)[
        "link_id"
    ]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    provider = device_climate.device.get_entity(
        Platform.CLIMATE, pick_first=True
    ).weekly_schedule
    clear = provider.async_clear
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_clear():
        started.set()
        await release.wait()
        return await clear()

    with patch.object(provider, "async_clear", side_effect=slow_clear):
        removal = asyncio.create_task(manager.async_remove_link(link_id))
        await asyncio.wait_for(started.wait(), 2)
        with pytest.raises(HomeAssistantError, match="already being changed"):
            await manager.async_update_link(link_id, "schedule.heating")
        with pytest.raises(HomeAssistantError, match="already being changed"):
            await manager.async_remove_link(link_id)
        with pytest.raises(HomeAssistantError, match="already being changed"):
            manager.async_request_sync(link_id)
        release.set()
        await removal

    await _write_heating_helper(client, 22, create=False)
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links() == []
    assert all(not values for values in stored.values())


@pytest.mark.parametrize("cancel", [False, True])
async def test_weekly_schedule_unsuccessful_removal_resumes_sync(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_climate,
    cancel: bool,
) -> None:
    """A failed or cancelled removal does not lose edits made while paused."""
    _enable_weekly_schedule(device_climate)
    stored, _ = _fake_schedule_device(device_climate)
    assert await async_setup_component(hass, "schedule", {})
    client = await hass_ws_client(hass)
    await _write_heating_helper(client, 18, create=True)
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)[
        "link_id"
    ]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    provider = device_climate.device.get_entity(
        Platform.CLIMATE, pick_first=True
    ).weekly_schedule
    started = asyncio.Event()
    release = asyncio.Event()

    async def failed_clear():
        started.set()
        await release.wait()
        raise ZHAException("clear failed")

    with patch.object(provider, "async_clear", side_effect=failed_clear):
        removal = asyncio.create_task(manager.async_remove_link(link_id))
        await asyncio.wait_for(started.wait(), 2)
        await _write_heating_helper(client, 22, create=False)
        if cancel:
            removal.cancel()
            with pytest.raises(asyncio.CancelledError):
                await removal
        else:
            release.set()
            with pytest.raises(HomeAssistantError, match="clear failed"):
                await removal

    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert stored[2] == [0, 1700, 360, 2200, 1320, 1700]
    assert manager.async_links()[0]["state"] == "synced"


async def test_weekly_schedule_failed_removal_restores_retry(
    hass: HomeAssistant, device_climate
) -> None:
    """A failed clear does not permanently cancel a device-error retry."""
    _enable_weekly_schedule(device_climate)
    stored, command = _fake_schedule_device(device_climate)
    working = command.side_effect
    command.side_effect = zigpy.exceptions.DeliveryError("offline")
    assert await async_setup_component(
        hass, "schedule", {"schedule": {"heating": {"name": "Heating"}}}
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)[
        "link_id"
    ]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "error"
    with pytest.raises(HomeAssistantError, match="Could not clear"):
        await manager.async_remove_link(link_id)
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "error"

    command.side_effect = working
    await _flush_sync(hass, RETRY_DELAY + timedelta(seconds=1))
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "synced"
    assert all(values == [0, 1700] for values in stored.values())


@pytest.mark.parametrize("state", [None, STATE_UNKNOWN, STATE_UNAVAILABLE])
async def test_weekly_schedule_remove_requires_known_mode(
    hass: HomeAssistant,
    device_climate,
    state: str | None,
) -> None:
    """Unknown or missing climate state must not be treated as non-Auto."""
    _enable_weekly_schedule(device_climate)
    stored, _ = _fake_schedule_device(device_climate)
    assert await async_setup_component(
        hass, "schedule", {"schedule": {"heating": {"name": "Heating"}}}
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)[
        "link_id"
    ]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    before = {day: values[:] for day, values in stored.items()}
    if state is None:
        hass.states.async_remove(entity_id)
    else:
        hass.states.async_set(entity_id, state)
    provider = device_climate.device.get_entity(
        Platform.CLIMATE, pick_first=True
    ).weekly_schedule

    with patch.object(provider, "async_clear") as clear:
        with pytest.raises(HomeAssistantError, match="unknown or unavailable"):
            await manager.async_remove_link(link_id)
        assert manager.async_links()
        await manager.async_remove_link(link_id, without_clearing=True)
        clear.assert_not_awaited()

    assert stored == before
    assert manager.async_links() == []


async def test_weekly_schedule_remove_missing_provider_requires_confirmation(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_climate,
) -> None:
    """Unlinking a missing thermostat requires an explicit no-clear request."""
    _enable_weekly_schedule(device_climate)
    stored, _ = _fake_schedule_device(device_climate)
    assert await async_setup_component(
        hass, "schedule", {"schedule": {"heating": {"name": "Heating"}}}
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)[
        "link_id"
    ]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    before = {day: values[:] for day, values in stored.items()}
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.zha.weekly_schedule._thermostat_provider",
        return_value=None,
    ):
        await client.send_json_auto_id(
            {"type": "zha/weekly_schedules/remove", "link_id": link_id}
        )
        response = await client.receive_json()
        assert response["error"]["code"] == "weekly_schedule_clear_failed"
        assert "not cleared" in response["error"]["message"]
        assert manager.async_links()
        await client.send_json_auto_id(
            {
                "type": "zha/weekly_schedules/remove",
                "link_id": link_id,
                "without_clearing": True,
            }
        )
        assert (await client.receive_json())["success"]

    assert stored == before
    assert manager.async_links() == []


async def test_weekly_schedule_subscriber_tracks_entity_references(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    device_climate,
) -> None:
    """Subscribers see supported entity registration, rename and removal."""
    _enable_weekly_schedule(device_climate)
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    gateway_proxy = get_zha_gateway_proxy(hass)
    reference = gateway_proxy.get_entity_reference(entity_id)
    assert reference is not None
    entity = next(
        platform.entities[entity_id]
        for platform in entity_platform.async_get_platforms(hass, ZHA_DOMAIN)
        if entity_id in platform.entities
    )
    gateway_proxy.remove_entity_reference(entity)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "zha/weekly_schedules/subscribe"})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["thermostats"] == []

    gateway_proxy.register_entity_reference(
        entity_id, reference.entity_data, reference.remove_future
    )
    assert (await client.receive_json())["event"]["thermostats"][0][
        "entity_id"
    ] == entity_id

    renamed_id = "climate.renamed_thermostat"
    entity_registry.async_update_entity(entity_id, new_entity_id=renamed_id)
    await hass.async_block_till_done()
    assert (await client.receive_json())["event"]["thermostats"][0][
        "entity_id"
    ] == renamed_id

    entity_registry.async_remove(renamed_id)
    await hass.async_block_till_done()
    assert (await client.receive_json())["event"]["thermostats"] == []


async def test_weekly_schedule_auto_requires_synced_link(
    hass: HomeAssistant, device_climate_mock
) -> None:
    """Auto is only offered while a linked helper was last synced successfully."""
    device_climate = await device_climate_mock(
        CLIMATE,
        {
            "ctrl_sequence_of_oper": Thermostat.ControlSequenceOfOperation.Heating_Only,
            "system_mode": Thermostat.SystemMode.Heat,
        },
    )
    _enable_weekly_schedule(device_climate)
    stored, command = _fake_schedule_device(device_climate)
    working = command.side_effect
    cluster = device_climate.device.device.endpoints[1].thermostat
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    # Refresh the cached ZHA state now that the schedule provider is exposed.
    await send_attributes_report(hass, cluster, {0: 2100})

    def modes() -> set[HVACMode]:
        return set(hass.states.get(entity_id).attributes[ATTR_HVAC_MODES])

    assert modes() == {HVACMode.OFF, HVACMode.HEAT}

    assert await async_setup_component(
        hass,
        "schedule",
        {"schedule": {"heating": {"name": "Heating", "monday": []}}},
    )
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)[
        "link_id"
    ]
    assert modes() == {HVACMode.OFF, HVACMode.HEAT}
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert all(values == [0, 1700] for values in stored.values())
    assert modes() == {HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO}

    command.side_effect = zigpy.exceptions.DeliveryError("offline")
    manager.async_request_sync(link_id)
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "error"
    assert modes() == {HVACMode.OFF, HVACMode.HEAT}
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.AUTO},
            blocking=True,
        )

    # A thermostat that already runs its schedule keeps Auto selectable.
    await send_attributes_report(hass, cluster, {0x001C: Thermostat.SystemMode.Auto})
    assert hass.states.get(entity_id).state == HVACMode.AUTO
    assert HVACMode.AUTO in modes()

    command.side_effect = working
    cluster.write_attributes.reset_mock()
    await manager.async_remove_link(link_id)
    # The thermostat leaves Auto before its schedule is cleared.
    assert cluster.write_attributes.call_args_list[0].args[0] == {
        "system_mode": Thermostat.SystemMode.Heat
    }
    assert all(values == [] for values in stored.values())
    assert hass.states.get(entity_id).state == HVACMode.HEAT
    assert modes() == {HVACMode.OFF, HVACMode.HEAT}


async def test_weekly_schedule_auto_after_standalone_upload(
    hass: HomeAssistant, device_climate_mock
) -> None:
    """A verified standalone upload offers Auto until the schedule is invalidated."""
    with patch(
        "zha.zigbee.device.BaseDevice._quirk_exposes_features",
        return_value={THERMOSTAT_WEEKLY_SCHEDULE},
    ):
        device_climate = await device_climate_mock(
            CLIMATE,
            {
                "ctrl_sequence_of_oper": Thermostat.ControlSequenceOfOperation.Heating_Only,
                "system_mode": Thermostat.SystemMode.Heat,
            },
        )
    _fake_schedule_device(device_climate)
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    days = {
        day: [{"from": "00:00", "to": "24:00", "data": {"temperature": 20}}]
        for day in WEEKDAY_TO_CONF.values()
    }
    assert await async_setup_component(
        hass,
        "schedule",
        {
            "schedule": {
                "heating": {"name": "Heating", **days},
                "empty": {"name": "Empty"},
            }
        },
    )

    def modes() -> set[HVACMode]:
        return set(hass.states.get(entity_id).attributes[ATTR_HVAC_MODES])

    async def upload() -> None:
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.SET_WEEKLY_SCHEDULE,
            {"entity_id": entity_id, "schedule_entity": "schedule.heating"},
            blocking=True,
        )

    async def raw_clear() -> None:
        await hass.services.async_call(
            ZHA_DOMAIN,
            ZHAService.ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {
                "ieee": str(device_climate.device.ieee),
                "endpoint_id": 1,
                "cluster_id": Thermostat.cluster_id,
                "command": 3,
                "command_type": "server",
                "params": {},
            },
            blocking=True,
        )

    assert modes() == {HVACMode.OFF, HVACMode.HEAT}
    await upload()
    assert HVACMode.AUTO in modes()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == HVACMode.AUTO
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    await hass.services.async_call(
        ZHA_DOMAIN,
        ZHAService.GET_WEEKLY_SCHEDULE,
        {"entity_id": entity_id},
        blocking=True,
        return_response=True,
    )
    assert HVACMode.AUTO in modes()
    await raw_clear()
    assert HVACMode.AUTO not in modes()
    await upload()
    assert HVACMode.AUTO in modes()
    await hass.services.async_call(
        ZHA_DOMAIN,
        ZHAService.CLEAR_WEEKLY_SCHEDULE,
        {"entity_id": entity_id},
        blocking=True,
    )
    assert HVACMode.AUTO not in modes()

    # An external write invalidates a link and causes the helper to be resynced.
    await upload()
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating")["link_id"]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert HVACMode.AUTO in modes()
    await raw_clear()
    assert manager.async_links()[0]["state"] == "pending"
    assert HVACMode.AUTO not in modes()
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "synced"
    assert HVACMode.AUTO in modes()

    # A verified schedule cannot bypass a failing linked helper.
    await manager.async_update_link(link_id, "schedule.empty")
    assert HVACMode.AUTO not in modes()
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "error"
    assert HVACMode.AUTO not in modes()


async def test_weekly_schedule_link_rejects_unsupported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_climate,
) -> None:
    """Thermostats without a schedule provider cannot be linked."""
    assert await async_setup_component(
        hass, "schedule", {"schedule": {"heating": {"name": "Heating"}}}
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "zha/weekly_schedules/list"})
    assert (await client.receive_json())["result"]["thermostats"] == []
    await client.send_json_auto_id(
        {
            "type": "zha/weekly_schedules/add",
            "thermostat_entity_id": entity_id,
            "schedule_entity_id": "schedule.heating",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert "does not support weekly schedules" in response["error"]["message"]

    _enable_weekly_schedule(device_climate)
    provider = device_climate.device.get_entity(
        Platform.CLIMATE, pick_first=True
    ).weekly_schedule
    with patch.object(
        provider, "capabilities", WeeklyScheduleCapabilities(supports_clear=False)
    ):
        await client.send_json_auto_id({"type": "zha/weekly_schedules/list"})
        assert (await client.receive_json())["result"]["thermostats"] == []
        await client.send_json_auto_id(
            {
                "type": "zha/weekly_schedules/add",
                "thermostat_entity_id": entity_id,
                "schedule_entity_id": "schedule.heating",
            }
        )
        response = await client.receive_json()
        assert not response["success"]
        assert "cannot clear weekly schedules" in response["error"]["message"]


async def test_weekly_schedule_link_repairs(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    issue_registry: ir.IssueRegistry,
    device_climate,
) -> None:
    """Sync failures retry and raise repairs; a deleted helper breaks the link."""
    _enable_weekly_schedule(device_climate)
    stored, command = _fake_schedule_device(device_climate)
    working = command.side_effect
    command.side_effect = zigpy.exceptions.DeliveryError("offline")
    assert await async_setup_component(hass, "schedule", {})
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "schedule/create",
            "name": "Heating",
            "monday": [
                {"from": "06:00:00", "to": "22:00:00", "data": {"temperature": 21}}
            ],
        }
    )
    assert (await client.receive_json())["success"]

    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating", gap_temperature=17)[
        "link_id"
    ]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "error"
    assert issue_registry.async_get_issue(ZHA_DOMAIN, f"{ISSUE_SYNC_FAILED}_{link_id}")

    command.side_effect = working
    await _flush_sync(hass, RETRY_DELAY + timedelta(seconds=1))
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    assert manager.async_links()[0]["state"] == "synced"
    assert stored[2] == [0, 1700, 360, 2100, 1320, 1700]
    assert not issue_registry.async_get_issue(
        ZHA_DOMAIN, f"{ISSUE_SYNC_FAILED}_{link_id}"
    )

    await client.send_json_auto_id(
        {"type": "schedule/delete", "schedule_id": "heating"}
    )
    assert (await client.receive_json())["success"]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    issue = issue_registry.async_get_issue(ZHA_DOMAIN, f"{ISSUE_LINK_BROKEN}_{link_id}")
    assert issue is not None
    assert issue.translation_placeholders["schedule"]

    await manager.async_remove_link(link_id)
    assert not issue_registry.async_get_issue(
        ZHA_DOMAIN, f"{ISSUE_LINK_BROKEN}_{link_id}"
    )


@pytest.mark.parametrize("unlink_without_clear", [False, True])
async def test_weekly_schedule_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    device_climate,
    unlink_without_clear: bool,
) -> None:
    """The sync repair can retry the sync or remove the link."""
    _enable_weekly_schedule(device_climate)
    stored, command = _fake_schedule_device(device_climate)
    stored[2][:] = [0, 2000]
    working = command.side_effect
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        "schedule",
        {"schedule": {"heating": {"name": "Heating", "monday": []}}},
    )
    entity_id = find_entity_id(Platform.CLIMATE, device_climate, hass)
    manager = get_zha_data(hass).weekly_schedule_sync
    link_id = manager.async_add_link(entity_id, "schedule.heating")["link_id"]
    await _flush_sync(hass, timedelta(seconds=SYNC_COOLDOWN + 1))
    issue_id = f"{ISSUE_SYNC_FAILED}_{link_id}"
    assert issue_registry.async_get_issue(ZHA_DOMAIN, issue_id).is_fixable
    client = await hass_client()

    async def fix(step: str) -> dict:
        resp = await client.post(
            "/api/repairs/issues/fix",
            json={"handler": ZHA_DOMAIN, "issue_id": issue_id},
        )
        data = await resp.json()
        assert data["step_id"] == "init"
        assert data["menu_options"] == ["retry", "remove_link"]
        assert data["description_placeholders"]["schedule"] == "schedule.heating"
        resp = await client.post(
            f"/api/repairs/issues/fix/{data['flow_id']}",
            json={"next_step_id": step},
        )
        await hass.async_block_till_done()
        return await resp.json()

    # Retrying with an unchanged helper fails again and keeps the issue.
    result = await fix("retry")
    assert result["type"] == "abort"
    assert result["reason"] == "sync_failed"
    assert "Monday" in result["description_placeholders"]["error"]
    assert issue_registry.async_get_issue(ZHA_DOMAIN, issue_id)

    # A failed clear keeps the link and explains the risks of unlinking.
    command.side_effect = zigpy.exceptions.DeliveryError("offline")
    result = await fix("remove_link")
    assert result["type"] == "form"
    assert result["step_id"] == "confirm_unlink"
    assert "Could not clear" in result["description_placeholders"]["error"]
    assert len(manager.async_links()) == 1

    if unlink_without_clear:
        resp = await client.post(
            f"/api/repairs/issues/fix/{result['flow_id']}", json={}
        )
        assert (await resp.json())["type"] == "create_entry"
        assert manager.async_links() == []
        assert stored[2] == [0, 2000]
        assert not issue_registry.async_get_issue(ZHA_DOMAIN, issue_id)
        return

    command.side_effect = working
    result = await fix("remove_link")
    assert result["type"] == "create_entry"
    assert manager.async_links() == []
    assert all(values == [] for values in stored.values())
    assert not issue_registry.async_get_issue(ZHA_DOMAIN, issue_id)
