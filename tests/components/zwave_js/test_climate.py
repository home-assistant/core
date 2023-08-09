"""Test the Z-Wave JS climate platform."""
import pytest
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.thermostat import (
    THERMOSTAT_OPERATING_STATE_PROPERTY,
)
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.node import Node

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.zwave_js.climate import ATTR_FAN_STATE
from homeassistant.components.zwave_js.const import DOMAIN, SERVICE_REFRESH_VALUE
from homeassistant.components.zwave_js.helpers import ZwaveValueMatcher
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .common import (
    CLIMATE_AIDOO_HVAC_UNIT_ENTITY,
    CLIMATE_DANFOSS_LC13_ENTITY,
    CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
    CLIMATE_FLOOR_THERMOSTAT_ENTITY,
    CLIMATE_MAIN_HEAT_ACTIONNER,
    CLIMATE_RADIO_THERMOSTAT_ENTITY,
    replace_value_of_zwave_value,
)


async def test_thermostat_v2(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a thermostat v2 command class entity."""
    node = climate_radio_thermostat_ct100_plus
    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)

    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    ]
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 30
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.2
    assert state.attributes[ATTR_TEMPERATURE] == 22.2
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert state.attributes[ATTR_FAN_MODE] == "Auto low"
    assert state.attributes[ATTR_FAN_STATE] == "Idle / off"
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
    )

    client.async_send_command.reset_mock()

    # Test setting hvac mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClass": 64,
        "endpoint": 1,
        "property": "mode",
    }
    assert args["value"] == 2

    client.async_send_command.reset_mock()

    # Test setting temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_HVAC_MODE: HVACMode.COOL,
            ATTR_TEMPERATURE: 25,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClass": 64,
        "endpoint": 1,
        "property": "mode",
    }
    assert args["value"] == 2
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClass": 67,
        "endpoint": 1,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 77

    client.async_send_command.reset_mock()

    # Test cool mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 13,
            "args": {
                "commandClassName": "Thermostat Mode",
                "commandClass": 64,
                "endpoint": 1,
                "property": "mode",
                "propertyName": "mode",
                "newValue": 2,
                "prevValue": 1,
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 22.8
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None

    # Test heat_cool mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 13,
            "args": {
                "commandClassName": "Thermostat Mode",
                "commandClass": 64,
                "endpoint": 1,
                "property": "mode",
                "propertyName": "mode",
                "newValue": 3,
                "prevValue": 1,
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 22.8
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 22.2

    client.async_send_command.reset_mock()

    # Test setting temperature with heat_cool
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_TARGET_TEMP_HIGH: 30,
            ATTR_TARGET_TEMP_LOW: 25,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClass": 67,
        "endpoint": 1,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 77

    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "commandClass": 67,
        "endpoint": 1,
        "property": "setpoint",
        "propertyKey": 2,
    }
    assert args["value"] == 86

    client.async_send_command.reset_mock()

    # Test setting invalid hvac mode
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )

    client.async_send_command.reset_mock()

    # Test setting fan mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
            ATTR_FAN_MODE: "Low",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 13
    assert args["valueId"] == {
        "endpoint": 1,
        "commandClass": 68,
        "property": "mode",
    }
    assert args["value"] == 1

    client.async_send_command.reset_mock()

    # Test setting invalid fan mode
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
                ATTR_FAN_MODE: "fake value",
            },
            blocking=True,
        )

    # Refresh value should log an error when there is an issue
    client.async_send_command.reset_mock()
    client.async_send_command.side_effect = FailedZWaveCommand("test", 1, "test")
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: CLIMATE_RADIO_THERMOSTAT_ENTITY,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert "Error while refreshing value" in caplog.text


async def test_thermostat_different_endpoints(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test an entity with values on a different endpoint from the primary value."""
    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)

    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.8
    assert state.attributes[ATTR_FAN_MODE] == "Auto low"
    assert state.attributes[ATTR_FAN_STATE] == "Idle / off"
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.COOLING


async def test_setpoint_thermostat(
    hass: HomeAssistant, client, climate_danfoss_lc_13, integration
) -> None:
    """Test a setpoint thermostat command class entity."""
    node = climate_danfoss_lc_13
    state = hass.states.get(CLIMATE_DANFOSS_LC13_ENTITY)

    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 14
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.HEAT]
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.TARGET_TEMPERATURE
    )

    client.async_send_command_no_wait.reset_mock()

    # Test setting temperature
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: CLIMATE_DANFOSS_LC13_ENTITY,
            ATTR_TEMPERATURE: 21.5,
        },
        blocking=True,
    )

    # Test setting illegal mode raises an error
    with pytest.raises(ValueError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_DANFOSS_LC13_ENTITY,
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )

    # Test that setting HVACMode.HEAT works. If the no-op logic didn't work, this would
    # raise an error
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_DANFOSS_LC13_ENTITY,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args_list[0][0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 67,
        "property": "setpoint",
        "propertyKey": 1,
    }
    assert args["value"] == 21.5

    client.async_send_command_no_wait.reset_mock()

    # Test setpoint mode update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 5,
            "args": {
                "commandClassName": "Thermostat Setpoint",
                "commandClass": 67,
                "endpoint": 0,
                "property": "setpoint",
                "propertyKey": 1,
                "propertyKeyName": "Heating",
                "propertyName": "setpoint",
                "newValue": 23,
                "prevValue": 21.5,
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(CLIMATE_DANFOSS_LC13_ENTITY)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 23

    client.async_send_command_no_wait.reset_mock()


async def test_thermostat_heatit_z_trm3_no_value(
    hass: HomeAssistant, client, climate_heatit_z_trm3_no_value, integration
) -> None:
    """Test a heatit Z-TRM3 entity that is missing a value."""
    # When the config parameter that specifies what sensor to use has no value, we fall
    # back to the first temperature sensor found on the device
    state = hass.states.get(CLIMATE_FLOOR_THERMOSTAT_ENTITY)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.5


async def test_thermostat_heatit_z_trm3(
    hass: HomeAssistant, client, climate_heatit_z_trm3, integration
) -> None:
    """Test a heatit Z-TRM3 entity."""
    node = climate_heatit_z_trm3
    state = hass.states.get(CLIMATE_FLOOR_THERMOSTAT_ENTITY)

    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT,
    ]
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.9
    assert state.attributes[ATTR_TEMPERATURE] == 22.5
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.TARGET_TEMPERATURE
    )
    assert state.attributes[ATTR_MIN_TEMP] == 5
    assert state.attributes[ATTR_MAX_TEMP] == 35

    # Try switching to external sensor
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 24,
            "args": {
                "commandClassName": "Configuration",
                "commandClass": 112,
                "endpoint": 0,
                "property": 2,
                "propertyName": "Sensor mode",
                "newValue": 4,
                "prevValue": 2,
            },
        },
    )
    node.receive_event(event)
    state = hass.states.get(CLIMATE_FLOOR_THERMOSTAT_ENTITY)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 0

    # Try switching to floor sensor
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 24,
            "args": {
                "commandClassName": "Configuration",
                "commandClass": 112,
                "endpoint": 0,
                "property": 2,
                "propertyName": "Sensor mode",
                "newValue": 0,
                "prevValue": 4,
            },
        },
    )
    node.receive_event(event)
    state = hass.states.get(CLIMATE_FLOOR_THERMOSTAT_ENTITY)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 25.5


async def test_thermostat_heatit_z_trm2fx(
    hass: HomeAssistant, client, climate_heatit_z_trm2fx, integration
) -> None:
    """Test a heatit Z-TRM2fx entity."""
    node = climate_heatit_z_trm2fx
    state = hass.states.get(CLIMATE_FLOOR_THERMOSTAT_ENTITY)

    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
    ]
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 28.8
    assert state.attributes[ATTR_TEMPERATURE] == 29
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    assert state.attributes[ATTR_MIN_TEMP] == 7
    assert state.attributes[ATTR_MAX_TEMP] == 35

    # Try switching to external sensor
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 24,
            "args": {
                "commandClassName": "Configuration",
                "commandClass": 112,
                "endpoint": 0,
                "property": 2,
                "propertyName": "Sensor mode",
                "newValue": 4,
                "prevValue": 2,
            },
        },
    )
    node.receive_event(event)
    state = hass.states.get(CLIMATE_FLOOR_THERMOSTAT_ENTITY)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 0


async def test_thermostat_srt321_hrt4_zw(
    hass: HomeAssistant, client, srt321_hrt4_zw, integration
) -> None:
    """Test a climate entity from a HRT4-ZW / SRT321 thermostat device.

    This device currently has no setpoint values.
    """
    state = hass.states.get(CLIMATE_MAIN_HEAT_ACTIONNER)

    assert state
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT,
    ]
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0


async def test_preset_and_no_setpoint(
    hass: HomeAssistant, client, climate_eurotronic_spirit_z, integration
) -> None:
    """Test preset without setpoint value."""
    node = climate_eurotronic_spirit_z

    state = hass.states.get(CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY)
    assert state
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 22

    # Test setting preset mode Full power
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
            ATTR_PRESET_MODE: "Full power",
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 8
    assert args["valueId"] == {
        "commandClass": 64,
        "endpoint": 0,
        "property": "mode",
    }
    assert args["value"] == 15

    client.async_send_command.reset_mock()

    # Test Full power preset update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 8,
            "args": {
                "commandClassName": "Thermostat Mode",
                "commandClass": 64,
                "endpoint": 0,
                "property": "mode",
                "propertyName": "mode",
                "newValue": 15,
                "prevValue": 1,
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] is None
    assert state.attributes[ATTR_PRESET_MODE] == "Full power"

    with pytest.raises(ValueError):
        # Test setting invalid preset mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
                ATTR_PRESET_MODE: "invalid_preset",
            },
            blocking=True,
        )

    assert len(client.async_send_command.call_args_list) == 0

    client.async_send_command.reset_mock()

    # Restore hvac mode by setting preset None
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_EUROTRONICS_SPIRIT_Z_ENTITY,
            ATTR_PRESET_MODE: PRESET_NONE,
        },
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 8
    assert args["valueId"]["commandClass"] == 64
    assert args["valueId"]["endpoint"] == 0
    assert args["valueId"]["property"] == "mode"
    assert args["value"] == 1

    client.async_send_command.reset_mock()


async def test_temp_unit_fix(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct101_multiple_temp_units,
    climate_radio_thermostat_ct100_mode_and_setpoint_on_different_endpoints,
    integration,
) -> None:
    """Test temperaturee unit fix."""
    state = hass.states.get("climate.thermostat")
    assert state
    assert state.attributes["current_temperature"] == 18.3

    state = hass.states.get("climate.z_wave_thermostat")
    assert state
    assert state.attributes["current_temperature"] == 21.1


async def test_thermostat_unknown_values(
    hass: HomeAssistant, client, climate_radio_thermostat_ct100_plus_state, integration
) -> None:
    """Test a thermostat v2 with unknown values."""
    node_state = replace_value_of_zwave_value(
        climate_radio_thermostat_ct100_plus_state,
        [
            ZwaveValueMatcher(
                THERMOSTAT_OPERATING_STATE_PROPERTY,
                command_class=CommandClass.THERMOSTAT_OPERATING_STATE,
            )
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()
    state = hass.states.get(CLIMATE_RADIO_THERMOSTAT_ENTITY)

    assert ATTR_HVAC_ACTION not in state.attributes


async def test_thermostat_dry_and_fan_both_hvac_mode_and_preset(
    hass: HomeAssistant,
    client,
    climate_airzone_aidoo_control_hvac_unit,
    integration,
) -> None:
    """Test that dry and fan modes are both available as hvac mode and preset."""
    state = hass.states.get(CLIMATE_AIDOO_HVAC_UNIT_ENTITY)
    assert state
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.HEAT_COOL,
    ]
    assert state.attributes[ATTR_PRESET_MODES] == [
        PRESET_NONE,
        "Fan",
        "Dry",
    ]


async def test_thermostat_raise_repair_issue_and_warning_when_setting_dry_preset(
    hass: HomeAssistant,
    client,
    climate_airzone_aidoo_control_hvac_unit,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test raise of repair issue and warning when setting Dry preset."""
    state = hass.states.get(CLIMATE_AIDOO_HVAC_UNIT_ENTITY)
    assert state

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_AIDOO_HVAC_UNIT_ENTITY,
            ATTR_PRESET_MODE: "Dry",
        },
        blocking=True,
    )

    issue_id = f"dry_fan_presets_deprecation_{CLIMATE_AIDOO_HVAC_UNIT_ENTITY}"
    issue_registry = ir.async_get(hass)

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=issue_id,
    )
    assert (
        "Dry and Fan preset modes are deprecated and will be removed in Home Assistant 2024.2. Please use the corresponding Dry and Fan HVAC modes instead"
        in caplog.text
    )


async def test_thermostat_raise_repair_issue_and_warning_when_setting_fan_preset(
    hass: HomeAssistant,
    client,
    climate_airzone_aidoo_control_hvac_unit,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test raise of repair issue and warning when setting Fan preset."""
    state = hass.states.get(CLIMATE_AIDOO_HVAC_UNIT_ENTITY)
    assert state

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: CLIMATE_AIDOO_HVAC_UNIT_ENTITY,
            ATTR_PRESET_MODE: "Fan",
        },
        blocking=True,
    )

    issue_id = f"dry_fan_presets_deprecation_{CLIMATE_AIDOO_HVAC_UNIT_ENTITY}"
    issue_registry = ir.async_get(hass)

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id=issue_id,
    )
    assert (
        "Dry and Fan preset modes are deprecated and will be removed in Home Assistant 2024.2. Please use the corresponding Dry and Fan HVAC modes instead"
        in caplog.text
    )
