"""Test entity discovery for device-specific schemas for the Z-Wave JS integration."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
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
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_aeon_smart_switch_6_state(
    hass: HomeAssistant, client, aeon_smart_switch_6, integration
) -> None:
    """Test that Smart Switch 6 has a meter reset button."""
    state = hass.states.get("button.smart_switch_6_reset_accumulated_values")
    assert state


async def test_iblinds_v2(hass: HomeAssistant, client, iblinds_v2, integration) -> None:
    """Test that an iBlinds v2.0 multilevel switch value is discovered as a cover."""
    node = iblinds_v2
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.window_blind_controller")
    assert not state

    state = hass.states.get("cover.window_blind_controller")
    assert state


async def test_touchwand_glass9(
    hass: HomeAssistant,
    client: MagicMock,
    touchwand_glass9: Node,
    integration: MockConfigEntry,
) -> None:
    """Test a touchwand_glass9 is discovered as a cover."""
    node = touchwand_glass9
    node_device_class = node.device_class
    assert node_device_class
    assert node_device_class.specific.label == "Unused"

    assert not hass.states.async_entity_ids_count("light")
    assert hass.states.async_entity_ids_count("cover") == 3
    state = hass.states.get("cover.gp9")
    assert state


async def test_zvidar_state(hass: HomeAssistant, client, zvidar, integration) -> None:
    """Test that an ZVIDAR Z-CM-V01 multilevel switch value is discovered as a cover."""
    node = zvidar
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


async def test_enbrighten_58446_zwa4013(
    hass: HomeAssistant, client, enbrighten_58446_zwa4013, integration
) -> None:
    """Test GE 12730 Fan Controller v2.0 multilevel switch is discovered as a fan."""
    node = enbrighten_58446_zwa4013
    assert node.device_class.specific.label == "Multilevel Power Switch"

    state = hass.states.get("light.zwa4013_fan")
    assert not state

    state = hass.states.get("fan.zwa4013_fan")
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
    assert hass.states.get("select.node_62_current_lock_mode") is not None


async def test_fortrez_ssa2_siren(
    hass: HomeAssistant,
    client: MagicMock,
    fortrezz_ssa2_siren: Node,
    integration: MockConfigEntry,
) -> None:
    """Test Fortrezz SSA2 siren gets discovered correctly."""
    assert hass.states.get("select.siren_and_strobe_alarm") is not None


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


async def test_shelly_001p10_disabled_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    shelly_qnsh_001P10_shutter,
    integration,
) -> None:
    """Test that Shelly 001P10 entity created by endpoint 2 is disabled."""
    entity_ids = [
        "cover.wave_shutter_2",
    ]
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is None
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Test enabling entity
        updated_entry = entity_registry.async_update_entity(
            entry.entity_id, disabled_by=None
        )
        assert updated_entry != entry
        assert updated_entry.disabled is False

    # Test if the main entity from endpoint 1 was created.
    state = hass.states.get("cover.wave_shutter")
    assert state


async def test_merten_507801_disabled_enitites(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    merten_507801,
    integration,
) -> None:
    """Test that Merten 507801 entities created by endpoint 2 are disabled."""
    entity_ids = [
        "cover.connect_roller_shutter_2",
        "select.connect_roller_shutter_local_protection_state_2",
        "select.connect_roller_shutter_rf_protection_state_2",
    ]
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is None
        entry = entity_registry.async_get(entity_id)
        assert entry
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        # Test enabling entity
        updated_entry = entity_registry.async_update_entity(
            entry.entity_id, disabled_by=None
        )
        assert updated_entry != entry
        assert updated_entry.disabled is False


@pytest.mark.parametrize("platforms", [[Platform.BUTTON, Platform.NUMBER]])
async def test_zooz_zen72(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    switch_zooz_zen72: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that Zooz ZEN72 Indicators are discovered as number entities."""
    entity_id = "number.z_wave_plus_700_series_dimmer_switch_indicator_value"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category == EntityCategory.CONFIG
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None  # disabled by default
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()
    client.async_send_command.reset_mock()
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
    assert client.async_send_command.call_count == 1
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
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category == EntityCategory.CONFIG
    assert entity_entry.disabled_by is None
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert client.async_send_command.call_count == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == switch_zooz_zen72.node_id
    assert args["valueId"] == {
        "commandClass": 135,
        "endpoint": 0,
        "property": "identify",
    }
    assert args["value"] is True


@pytest.mark.parametrize(
    "platforms", [[Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]]
)
async def test_indicator_test(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    indicator_test: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that Indicators are discovered properly.

    This test covers indicators that we don't already have device fixtures for.
    """
    binary_sensor_entity_id = "binary_sensor.this_is_a_fake_device_binary_sensor"
    sensor_entity_id = "sensor.this_is_a_fake_device_sensor"
    switch_entity_id = "switch.this_is_a_fake_device_switch"

    for entity_id in (
        binary_sensor_entity_id,
        sensor_entity_id,
    ):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry
        assert entity_entry.entity_category == EntityCategory.DIAGNOSTIC
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None  # disabled by default
        entity_registry.async_update_entity(entity_id, disabled_by=None)

    entity_id = switch_entity_id
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category == EntityCategory.CONFIG
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None  # disabled by default
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()
    client.async_send_command.reset_mock()

    entity_id = binary_sensor_entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entity_id = sensor_entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "0.0"

    entity_id = switch_entity_id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert client.async_send_command.call_count == 1
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
    assert client.async_send_command.call_count == 1
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


async def test_light_device_class_is_null(
    hass: HomeAssistant, client, light_device_class_is_null, integration
) -> None:
    """Test that a Multilevel Switch CC value with a null device class is discovered as a light.

    Tied to #117121.
    """
    node = light_device_class_is_null
    assert node.device_class is None
    assert hass.states.get("light.bar_display_cases")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rediscovery(
    hass: HomeAssistant,
    siren_neo_coolcam: Node,
    integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we don't rediscover known values."""
    node = siren_neo_coolcam
    entity_id = "select.siren_alarm_doorbell_sound_selection"
    state = hass.states.get(entity_id)

    assert state
    assert state.state == "Beep"

    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 36,
            "args": {
                "commandClassName": "Configuration",
                "commandClass": 112,
                "endpoint": 0,
                "property": 6,
                "newValue": 9,
                "prevValue": 10,
                "propertyName": "Doorbell Sound Selection",
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "Beep Beep"
    assert "Platform zwave_js does not generate unique IDs" not in caplog.text


async def test_aeotec_smart_switch_7(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aeotec_smart_switch_7: Node,
    integration: MockConfigEntry,
) -> None:
    """Test Smart Switch 7 discovery."""
    state = hass.states.get("light.smart_switch_7")
    assert state
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [
        ColorMode.HS,
    ]

    state = hass.states.get("switch.smart_switch_7")
    assert state

    state = hass.states.get("button.smart_switch_7_reset_accumulated_values")
    assert state
    entity_entry = entity_registry.async_get(state.entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG


async def test_nabu_casa_zwa2(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    nabu_casa_zwa2: Node,
    integration: MockConfigEntry,
) -> None:
    """Test ZWA-2 discovery."""
    state = hass.states.get("light.home_assistant_connect_zwa_2_led")
    assert state, "The LED indicator should be enabled by default"

    entry = entity_registry.async_get(state.entity_id)
    assert entry, "Entity for the LED indicator not found"

    assert entry.capabilities.get(ATTR_SUPPORTED_COLOR_MODES) == [
        ColorMode.ONOFF,
    ], "The LED indicator should be an ON/OFF light"

    assert not entry.disabled, "The entity should be enabled by default"

    assert entry.entity_category is EntityCategory.CONFIG, (
        "The LED indicator should be configuration"
    )

    # Test that the entity name is properly set to "LED"
    assert entry.original_name == "LED", (
        "The LED entity should have the original name 'LED'"
    )
    assert state.attributes["friendly_name"] == "Home Assistant Connect ZWA-2 LED", (
        "The LED should have the correct friendly name"
    )


async def test_nabu_casa_zwa2_legacy(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    nabu_casa_zwa2_legacy: Node,
    integration: MockConfigEntry,
) -> None:
    """Test ZWA-2 discovery with legacy firmware."""
    state = hass.states.get("light.home_assistant_connect_zwa_2_led")
    assert state, "The LED indicator should be enabled by default"

    entry = entity_registry.async_get(state.entity_id)
    assert entry, "Entity for the LED indicator not found"

    assert entry.capabilities.get(ATTR_SUPPORTED_COLOR_MODES) == [
        ColorMode.HS,
    ], "The LED indicator should be a color light"

    assert not entry.disabled, "The entity should be enabled by default"

    assert entry.entity_category is EntityCategory.CONFIG, (
        "The LED indicator should be configuration"
    )

    # Test that the entity name is properly set to "LED"
    assert entry.original_name == "LED", (
        "The LED entity should have the original name 'LED'"
    )
    assert state.attributes["friendly_name"] == "Home Assistant Connect ZWA-2 LED", (
        "The LED should have the correct friendly name"
    )
