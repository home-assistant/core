"""Test ZHA climate."""

from typing import Literal
from unittest.mock import patch

import pytest
from zha.application.platforms.climate.const import HVAC_MODE_2_SYSTEM, SEQ_OF_OPERATION
import zhaquirks.sinope.thermostat
import zhaquirks.tuya.ts0601_trv
import zigpy.profiles
from zigpy.profiles import zha
import zigpy.types
import zigpy.zcl.clusters
from zigpy.zcl.clusters.hvac import Thermostat

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
from homeassistant.components.zha.helpers import (
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

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
def device_climate_mock(hass: HomeAssistant, setup_zha, zigpy_device_mock):
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

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    if sys_mode is not None:
        assert state.state == hvac_mode
        assert thrm_cluster.write_attributes.call_count == 1
        assert thrm_cluster.write_attributes.call_args[0][0] == {
            "system_mode": sys_mode
        }
    else:
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
