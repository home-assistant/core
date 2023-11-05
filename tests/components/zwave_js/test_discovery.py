"""Test entity discovery for device-specific schemas for the Z-Wave JS integration."""
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.zwave_js.discovery import (
    FirmwareVersionRange,
    ZWaveDiscoverySchema,
    ZWaveValueDiscoverySchema,
)
from homeassistant.components.zwave_js.discovery_data_template import (
    DynamicCurrentTempClimateDataTemplate,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_iblinds_v2(hass: HomeAssistant, client, iblinds_v2, integration) -> None:
    """Test that an iBlinds v2.0 multilevel switch value is discovered as a cover."""
    node = iblinds_v2
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.window_blind_controller")
    assert not state

    state = hass.states.get("cover.window_blind_controller")
    assert state


async def test_ge_12730(hass: HomeAssistant, client, ge_12730, integration) -> None:
    """Test GE 12730 Fan Controller v2.0 multilevel switch is discovered as a fan."""
    node = ge_12730
    assert node.device_class.specific.label == "Multilevel Power Switch"

    state = hass.states.get("light.in_wall_smart_fan_control")
    assert not state

    state = hass.states.get("fan.in_wall_smart_fan_control")
    assert state


async def test_inovelli_lzw36(
    hass: HomeAssistant, client, inovelli_lzw36, integration
) -> None:
    """Test LZW36 Fan Controller multilevel switch endpoint 2 is discovered as a fan."""
    node = inovelli_lzw36
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.family_room_combo")
    assert state.state == "off"

    state = hass.states.get("fan.family_room_combo_2")
    assert state


async def test_vision_security_zl7432(
    hass: HomeAssistant, client, vision_security_zl7432, integration
) -> None:
    """Test Vision Security ZL7432 is caught by the device specific discovery."""
    for entity_id in (
        "switch.in_wall_dual_relay_switch",
        "switch.in_wall_dual_relay_switch_2",
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["assumed_state"]


async def test_lock_popp_electric_strike_lock_control(
    hass: HomeAssistant, client, lock_popp_electric_strike_lock_control, integration
) -> None:
    """Test that the Popp Electric Strike Lock Control gets discovered correctly."""
    assert hass.states.get("lock.node_62") is not None
    assert (
        hass.states.get("binary_sensor.node_62_the_current_status_of_the_door")
        is not None
    )


async def test_fortrez_ssa3_siren(
    hass: HomeAssistant, client, fortrezz_ssa3_siren, integration
) -> None:
    """Test Fortrezz SSA3 siren gets discovered correctly."""
    assert hass.states.get("select.siren_and_strobe_alarm") is not None


async def test_firmware_version_range_exception(hass: HomeAssistant) -> None:
    """Test FirmwareVersionRange exception."""
    with pytest.raises(ValueError):
        ZWaveDiscoverySchema(
            "test",
            ZWaveValueDiscoverySchema(command_class=1),
            firmware_version_range=FirmwareVersionRange(),
        )


async def test_dynamic_climate_data_discovery_template_failure(
    hass: HomeAssistant, multisensor_6
) -> None:
    """Test that initing a DynamicCurrentTempClimateDataTemplate with no data raises."""
    node = multisensor_6
    with pytest.raises(ValueError):
        DynamicCurrentTempClimateDataTemplate().resolve_data(
            node.values[f"{node.node_id}-49-0-Ultraviolet"]
        )


async def test_merten_507801(
    hass: HomeAssistant, client, merten_507801, integration
) -> None:
    """Test that Merten 507801 multilevel switch value is discovered as a cover."""
    node = merten_507801
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.connect_roller_shutter")
    assert not state

    state = hass.states.get("cover.connect_roller_shutter")
    assert state


async def test_merten_507801_disabled_enitites(
    hass: HomeAssistant, client, merten_507801, integration
) -> None:
    """Test that Merten 507801 entities created by endpoint 2 are disabled."""
    registry = er.async_get(hass)
    entity_ids = [
        "cover.connect_roller_shutter_2",
        "select.connect_roller_shutter_local_protection_state_2",
        "select.connect_roller_shutter_rf_protection_state_2",
    ]
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is None
        entry = registry.async_get(entity_id)
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Test enabling entity
        updated_entry = registry.async_update_entity(
            entry.entity_id, **{"disabled_by": None}
        )
        assert updated_entry != entry
        assert updated_entry.disabled is False


async def test_zooz_zen72(
    hass: HomeAssistant, client, switch_zooz_zen72, integration
) -> None:
    """Test that Zooz ZEN72 Indicators are discovered as number entities."""
    ent_reg = er.async_get(hass)
    assert len(hass.states.async_entity_ids(NUMBER_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 2  # includes ping
    entity_id = "number.z_wave_plus_700_series_dimmer_switch_indicator_value"
    entry = ent_reg.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.CONFIG
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 5,
        },
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == switch_zooz_zen72.node_id
    assert args["valueId"] == {
        "commandClass": 135,
        "endpoint": 0,
        "property": "value",
    }
    assert args["value"] == 5

    client.async_send_command.reset_mock()

    entity_id = "button.z_wave_plus_700_series_dimmer_switch_identify"
    entry = ent_reg.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.CONFIG
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == switch_zooz_zen72.node_id
    assert args["valueId"] == {
        "commandClass": 135,
        "endpoint": 0,
        "property": "identify",
    }
    assert args["value"] is True


async def test_indicator_test(
    hass: HomeAssistant, client, indicator_test, integration
) -> None:
    """Test that Indicators are discovered properly.

    This test covers indicators that we don't already have device fixtures for.
    """
    ent_reg = er.async_get(hass)
    assert len(hass.states.async_entity_ids(NUMBER_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(BUTTON_DOMAIN)) == 1  # only ping
    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1
    assert (
        len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
    )  # include node + controller status
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    entity_id = "binary_sensor.this_is_a_fake_device_binary_sensor"
    entry = ent_reg.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    client.async_send_command.reset_mock()

    entity_id = "sensor.this_is_a_fake_device_sensor"
    entry = ent_reg.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.0"

    client.async_send_command.reset_mock()

    entity_id = "switch.this_is_a_fake_device_switch"
    entry = ent_reg.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.CONFIG
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == indicator_test.node_id
    assert args["valueId"] == {
        "commandClass": 135,
        "endpoint": 0,
        "property": "Test",
        "propertyKey": "Switch",
    }
    assert args["value"] is True

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == indicator_test.node_id
    assert args["valueId"] == {
        "commandClass": 135,
        "endpoint": 0,
        "property": "Test",
        "propertyKey": "Switch",
    }
    assert args["value"] is False
