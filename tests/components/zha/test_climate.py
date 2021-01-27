"""Test zha climate."""

from unittest.mock import patch

import pytest
import zigpy.zcl.clusters
from zigpy.zcl.clusters.hvac import Thermostat
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_FAN,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.zha.climate import (
    DOMAIN,
    HVAC_MODE_2_SYSTEM,
    SEQ_OF_OPERATION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, STATE_UNKNOWN

from .common import async_enable_traffic, find_entity_id, send_attributes_report

CLIMATE = {
    1: {
        "device_type": zigpy.profiles.zha.DeviceType.THERMOSTAT,
        "in_clusters": [
            zigpy.zcl.clusters.general.Basic.cluster_id,
            zigpy.zcl.clusters.general.Identify.cluster_id,
            zigpy.zcl.clusters.hvac.Thermostat.cluster_id,
            zigpy.zcl.clusters.hvac.UserInterface.cluster_id,
        ],
        "out_clusters": [zigpy.zcl.clusters.general.Ota.cluster_id],
    }
}

CLIMATE_FAN = {
    1: {
        "device_type": zigpy.profiles.zha.DeviceType.THERMOSTAT,
        "in_clusters": [
            zigpy.zcl.clusters.general.Basic.cluster_id,
            zigpy.zcl.clusters.general.Identify.cluster_id,
            zigpy.zcl.clusters.hvac.Fan.cluster_id,
            zigpy.zcl.clusters.hvac.Thermostat.cluster_id,
            zigpy.zcl.clusters.hvac.UserInterface.cluster_id,
        ],
        "out_clusters": [zigpy.zcl.clusters.general.Ota.cluster_id],
    }
}

CLIMATE_SINOPE = {
    1: {
        "device_type": zigpy.profiles.zha.DeviceType.THERMOSTAT,
        "in_clusters": [
            zigpy.zcl.clusters.general.Basic.cluster_id,
            zigpy.zcl.clusters.general.Identify.cluster_id,
            zigpy.zcl.clusters.hvac.Thermostat.cluster_id,
            zigpy.zcl.clusters.hvac.UserInterface.cluster_id,
            65281,
        ],
        "out_clusters": [zigpy.zcl.clusters.general.Ota.cluster_id, 65281],
        "profile_id": 260,
    },
}

CLIMATE_ZEN = {
    1: {
        "device_type": zigpy.profiles.zha.DeviceType.THERMOSTAT,
        "in_clusters": [
            zigpy.zcl.clusters.general.Basic.cluster_id,
            zigpy.zcl.clusters.general.Identify.cluster_id,
            zigpy.zcl.clusters.hvac.Fan.cluster_id,
            zigpy.zcl.clusters.hvac.Thermostat.cluster_id,
            zigpy.zcl.clusters.hvac.UserInterface.cluster_id,
        ],
        "out_clusters": [zigpy.zcl.clusters.general.Ota.cluster_id],
    }
}
MANUF_SINOPE = "Sinope Technologies"
MANUF_ZEN = "Zen Within"

ZCL_ATTR_PLUG = {
    "abs_min_heat_setpoint_limit": 800,
    "abs_max_heat_setpoint_limit": 3000,
    "abs_min_cool_setpoint_limit": 2000,
    "abs_max_cool_setpoint_limit": 4000,
    "ctrl_seqe_of_oper": Thermostat.ControlSequenceOfOperation.Cooling_and_Heating,
    "local_temp": None,
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


@pytest.fixture
def device_climate_mock(hass, zigpy_device_mock, zha_device_joined):
    """Test regular thermostat device."""

    async def _dev(clusters, plug=None, manuf=None):
        if plug is None:
            plugged_attrs = ZCL_ATTR_PLUG
        else:
            plugged_attrs = {**ZCL_ATTR_PLUG, **plug}

        zigpy_device = zigpy_device_mock(clusters, manufacturer=manuf)
        zigpy_device.endpoints[1].thermostat.PLUGGED_ATTR_READS = plugged_attrs
        zha_device = await zha_device_joined(zigpy_device)
        await async_enable_traffic(hass, [zha_device])
        await hass.async_block_till_done()
        return zha_device

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

    return await device_climate_mock(CLIMATE_SINOPE, manuf=MANUF_SINOPE)


@pytest.fixture
async def device_climate_zen(device_climate_mock):
    """Zen Within thermostat."""

    return await device_climate_mock(CLIMATE_ZEN, manuf=MANUF_ZEN)


def test_sequence_mappings():
    """Test correct mapping between control sequence -> HVAC Mode -> Sysmode."""

    for hvac_modes in SEQ_OF_OPERATION.values():
        for hvac_mode in hvac_modes:
            assert hvac_mode in HVAC_MODE_2_SYSTEM
            assert Thermostat.SystemMode(HVAC_MODE_2_SYSTEM[hvac_mode]) is not None


async def test_climate_local_temp(hass, device_climate):
    """Test local temperature."""

    thrm_cluster = device_climate.device.endpoints[1].thermostat
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None

    await send_attributes_report(hass, thrm_cluster, {0: 2100})
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.0


async def test_climate_hvac_action_running_state(hass, device_climate):
    """Test hvac action via running state."""

    thrm_cluster = device_climate.device.endpoints[1].thermostat
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Off}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Auto}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Cool}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Heat}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT

    await send_attributes_report(
        hass, thrm_cluster, {0x001E: Thermostat.RunningMode.Off}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Fan_State_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_FAN


async def test_climate_hvac_action_running_state_zen(hass, device_climate_zen):
    """Test Zen hvac action via running state."""

    thrm_cluster = device_climate_zen.device.endpoints[1].thermostat
    entity_id = await find_entity_id(DOMAIN, device_climate_zen, hass)

    state = hass.states.get(entity_id)
    assert ATTR_HVAC_ACTION not in state.attributes

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Cool_2nd_Stage_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Fan_State_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_FAN

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Heat_2nd_Stage_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Fan_2nd_Stage_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_FAN

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Cool_State_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Fan_3rd_Stage_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_FAN

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Heat_State_On}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT

    await send_attributes_report(
        hass, thrm_cluster, {0x0029: Thermostat.RunningState.Idle}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Heat}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE


async def test_climate_hvac_action_pi_demand(hass, device_climate):
    """Test hvac action based on pi_heating/cooling_demand attrs."""

    thrm_cluster = device_climate.device.endpoints[1].thermostat
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    await send_attributes_report(hass, thrm_cluster, {0x0007: 10})
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL

    await send_attributes_report(hass, thrm_cluster, {0x0008: 20})
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT

    await send_attributes_report(hass, thrm_cluster, {0x0007: 0})
    await send_attributes_report(hass, thrm_cluster, {0x0008: 0})

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_OFF

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Heat}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Cool}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE


@pytest.mark.parametrize(
    "sys_mode, hvac_mode",
    (
        (Thermostat.SystemMode.Auto, HVAC_MODE_HEAT_COOL),
        (Thermostat.SystemMode.Cool, HVAC_MODE_COOL),
        (Thermostat.SystemMode.Heat, HVAC_MODE_HEAT),
        (Thermostat.SystemMode.Pre_cooling, HVAC_MODE_COOL),
        (Thermostat.SystemMode.Fan_only, HVAC_MODE_FAN_ONLY),
        (Thermostat.SystemMode.Dry, HVAC_MODE_DRY),
    ),
)
async def test_hvac_mode(hass, device_climate, sys_mode, hvac_mode):
    """Test HVAC modee."""

    thrm_cluster = device_climate.device.endpoints[1].thermostat
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_OFF

    await send_attributes_report(hass, thrm_cluster, {0x001C: sys_mode})
    state = hass.states.get(entity_id)
    assert state.state == hvac_mode

    await send_attributes_report(
        hass, thrm_cluster, {0x001C: Thermostat.SystemMode.Off}
    )
    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_OFF

    await send_attributes_report(hass, thrm_cluster, {0x001C: 0xFF})
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "seq_of_op, modes",
    (
        (0xFF, {HVAC_MODE_OFF}),
        (0x00, {HVAC_MODE_OFF, HVAC_MODE_COOL}),
        (0x01, {HVAC_MODE_OFF, HVAC_MODE_COOL}),
        (0x02, {HVAC_MODE_OFF, HVAC_MODE_HEAT}),
        (0x03, {HVAC_MODE_OFF, HVAC_MODE_HEAT}),
        (0x04, {HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL}),
        (0x05, {HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL}),
    ),
)
async def test_hvac_modes(hass, device_climate_mock, seq_of_op, modes):
    """Test HVAC modes from sequence of operations."""

    device_climate = await device_climate_mock(
        CLIMATE, {"ctrl_seqe_of_oper": seq_of_op}
    )
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    state = hass.states.get(entity_id)
    assert set(state.attributes[ATTR_HVAC_MODES]) == modes


@pytest.mark.parametrize(
    "sys_mode, preset, target_temp",
    (
        (Thermostat.SystemMode.Heat, None, 22),
        (Thermostat.SystemMode.Heat, PRESET_AWAY, 16),
        (Thermostat.SystemMode.Cool, None, 25),
        (Thermostat.SystemMode.Cool, PRESET_AWAY, 27),
    ),
)
async def test_target_temperature(
    hass, device_climate_mock, sys_mode, preset, target_temp
):
    """Test target temperature property."""

    with patch.object(
        zigpy.zcl.clusters.manufacturer_specific.ManufacturerSpecificCluster,
        "ep_attribute",
        "sinope_manufacturer_specific",
    ):
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
        )
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    if preset:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == target_temp


@pytest.mark.parametrize(
    "preset, unoccupied, target_temp",
    (
        (None, 1800, 17),
        (PRESET_AWAY, 1800, 18),
        (PRESET_AWAY, None, None),
    ),
)
async def test_target_temperature_high(
    hass, device_climate_mock, preset, unoccupied, target_temp
):
    """Test target temperature high property."""

    with patch.object(
        zigpy.zcl.clusters.manufacturer_specific.ManufacturerSpecificCluster,
        "ep_attribute",
        "sinope_manufacturer_specific",
    ):
        device_climate = await device_climate_mock(
            CLIMATE_SINOPE,
            {
                "occupied_cooling_setpoint": 1700,
                "system_mode": Thermostat.SystemMode.Auto,
                "unoccupied_cooling_setpoint": unoccupied,
            },
            manuf=MANUF_SINOPE,
        )
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    if preset:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == target_temp


@pytest.mark.parametrize(
    "preset, unoccupied, target_temp",
    (
        (None, 1600, 21),
        (PRESET_AWAY, 1600, 16),
        (PRESET_AWAY, None, None),
    ),
)
async def test_target_temperature_low(
    hass, device_climate_mock, preset, unoccupied, target_temp
):
    """Test target temperature low property."""

    with patch.object(
        zigpy.zcl.clusters.manufacturer_specific.ManufacturerSpecificCluster,
        "ep_attribute",
        "sinope_manufacturer_specific",
    ):
        device_climate = await device_climate_mock(
            CLIMATE_SINOPE,
            {
                "occupied_heating_setpoint": 2100,
                "system_mode": Thermostat.SystemMode.Auto,
                "unoccupied_heating_setpoint": unoccupied,
            },
            manuf=MANUF_SINOPE,
        )
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    if preset:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
            blocking=True,
        )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == target_temp


@pytest.mark.parametrize(
    "hvac_mode, sys_mode",
    (
        (HVAC_MODE_AUTO, None),
        (HVAC_MODE_COOL, Thermostat.SystemMode.Cool),
        (HVAC_MODE_DRY, None),
        (HVAC_MODE_FAN_ONLY, None),
        (HVAC_MODE_HEAT, Thermostat.SystemMode.Heat),
        (HVAC_MODE_HEAT_COOL, Thermostat.SystemMode.Auto),
    ),
)
async def test_set_hvac_mode(hass, device_climate, hvac_mode, sys_mode):
    """Test setting hvac mode."""

    thrm_cluster = device_climate.device.endpoints[1].thermostat
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_OFF

    await hass.services.async_call(
        DOMAIN,
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
        assert state.state == HVAC_MODE_OFF

    # turn off
    thrm_cluster.write_attributes.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVAC_MODE_OFF},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_OFF
    assert thrm_cluster.write_attributes.call_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {
        "system_mode": Thermostat.SystemMode.Off
    }


async def test_preset_setting(hass, device_climate_sinope):
    """Test preset setting."""

    entity_id = await find_entity_id(DOMAIN, device_climate_sinope, hass)
    thrm_cluster = device_climate_sinope.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    # unsuccessful occupancy change
    thrm_cluster.write_attributes.return_value = [
        zcl_f.WriteAttributesResponse.deserialize(b"\x01\x00\x00")[0]
    ]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thrm_cluster.write_attributes.call_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {"set_occupancy": 0}

    # successful occupancy change
    thrm_cluster.write_attributes.reset_mock()
    thrm_cluster.write_attributes.return_value = [
        zcl_f.WriteAttributesResponse.deserialize(b"\x00")[0]
    ]
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY
    assert thrm_cluster.write_attributes.call_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {"set_occupancy": 0}

    # unsuccessful occupancy change
    thrm_cluster.write_attributes.reset_mock()
    thrm_cluster.write_attributes.return_value = [
        zcl_f.WriteAttributesResponse.deserialize(b"\x01\x01\x01")[0]
    ]
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY
    assert thrm_cluster.write_attributes.call_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {"set_occupancy": 1}

    # successful occupancy change
    thrm_cluster.write_attributes.reset_mock()
    thrm_cluster.write_attributes.return_value = [
        zcl_f.WriteAttributesResponse.deserialize(b"\x00")[0]
    ]
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thrm_cluster.write_attributes.call_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {"set_occupancy": 1}


async def test_preset_setting_invalid(hass, device_climate_sinope):
    """Test invalid preset setting."""

    entity_id = await find_entity_id(DOMAIN, device_climate_sinope, hass)
    thrm_cluster = device_climate_sinope.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: "invalid_preset"},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE
    assert thrm_cluster.write_attributes.call_count == 0


async def test_set_temperature_hvac_mode(hass, device_climate):
    """Test setting HVAC mode in temperature service call."""

    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    thrm_cluster = device_climate.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_OFF

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HVAC_MODE: HVAC_MODE_HEAT_COOL,
            ATTR_TEMPERATURE: 20,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_HEAT_COOL
    assert thrm_cluster.write_attributes.await_count == 1
    assert thrm_cluster.write_attributes.call_args[0][0] == {
        "system_mode": Thermostat.SystemMode.Auto
    }


async def test_set_temperature_heat_cool(hass, device_climate_mock):
    """Test setting temperature service call in heating/cooling HVAC mode."""

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
                "system_mode": Thermostat.SystemMode.Auto,
                "unoccupied_heating_setpoint": 1600,
                "unoccupied_cooling_setpoint": 2700,
            },
            manuf=MANUF_SINOPE,
        )
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    thrm_cluster = device_climate.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_HEAT_COOL

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 21},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 20.0
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 25.0
    assert thrm_cluster.write_attributes.await_count == 0

    await hass.services.async_call(
        DOMAIN,
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
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    thrm_cluster.write_attributes.reset_mock()

    await hass.services.async_call(
        DOMAIN,
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


async def test_set_temperature_heat(hass, device_climate_mock):
    """Test setting temperature service call in heating HVAC mode."""

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
                "system_mode": Thermostat.SystemMode.Heat,
                "unoccupied_heating_setpoint": 1600,
                "unoccupied_cooling_setpoint": 2700,
            },
            manuf=MANUF_SINOPE,
        )
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    thrm_cluster = device_climate.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_HEAT

    await hass.services.async_call(
        DOMAIN,
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
        DOMAIN,
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
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    thrm_cluster.write_attributes.reset_mock()

    await hass.services.async_call(
        DOMAIN,
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


async def test_set_temperature_cool(hass, device_climate_mock):
    """Test setting temperature service call in cooling HVAC mode."""

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
                "system_mode": Thermostat.SystemMode.Cool,
                "unoccupied_cooling_setpoint": 1600,
                "unoccupied_heating_setpoint": 2700,
            },
            manuf=MANUF_SINOPE,
        )
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    thrm_cluster = device_climate.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_COOL

    await hass.services.async_call(
        DOMAIN,
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
        DOMAIN,
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
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    thrm_cluster.write_attributes.reset_mock()

    await hass.services.async_call(
        DOMAIN,
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


async def test_set_temperature_wrong_mode(hass, device_climate_mock):
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
    entity_id = await find_entity_id(DOMAIN, device_climate, hass)
    thrm_cluster = device_climate.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_DRY

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 24},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert thrm_cluster.write_attributes.await_count == 0


async def test_occupancy_reset(hass, device_climate_sinope):
    """Test away preset reset."""

    entity_id = await find_entity_id(DOMAIN, device_climate_sinope, hass)
    thrm_cluster = device_climate_sinope.device.endpoints[1].thermostat

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    thrm_cluster.write_attributes.reset_mock()

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY

    await send_attributes_report(
        hass, thrm_cluster, {"occupied_heating_setpoint": 1950}
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_NONE


async def test_fan_mode(hass, device_climate_fan):
    """Test fan mode."""

    entity_id = await find_entity_id(DOMAIN, device_climate_fan, hass)
    thrm_cluster = device_climate_fan.device.endpoints[1].thermostat

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


async def test_set_fan_mode_not_supported(hass, device_climate_fan):
    """Test fan setting unsupported mode."""

    entity_id = await find_entity_id(DOMAIN, device_climate_fan, hass)
    fan_cluster = device_climate_fan.device.endpoints[1].fan

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )
    assert fan_cluster.write_attributes.await_count == 0


async def test_set_fan_mode(hass, device_climate_fan):
    """Test fan mode setting."""

    entity_id = await find_entity_id(DOMAIN, device_climate_fan, hass)
    fan_cluster = device_climate_fan.device.endpoints[1].fan

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_ON},
        blocking=True,
    )
    assert fan_cluster.write_attributes.await_count == 1
    assert fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 4}

    fan_cluster.write_attributes.reset_mock()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_MODE: FAN_AUTO},
        blocking=True,
    )
    assert fan_cluster.write_attributes.await_count == 1
    assert fan_cluster.write_attributes.call_args[0][0] == {"fan_mode": 5}
