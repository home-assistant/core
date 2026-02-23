"""Test Matter locks."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_climates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climates."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.CLIMATE)


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_thermostat_base(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat base attributes and state updates."""
    # test entity attributes
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["min_temp"] == 7
    assert state.attributes["max_temp"] == 35
    assert state.attributes["temperature"] is None
    assert state.state == HVACMode.COOL

    # test supported features correctly parsed
    # including temperature_range support
    mask = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    assert state.attributes["supported_features"] & mask == mask

    # test common state updates from device
    set_node_attribute(matter_node, 1, 513, 3, 1600)
    set_node_attribute(matter_node, 1, 513, 4, 3000)
    set_node_attribute(matter_node, 1, 513, 5, 1600)
    set_node_attribute(matter_node, 1, 513, 6, 3000)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["min_temp"] == 16
    assert state.attributes["max_temp"] == 30
    assert state.attributes["hvac_modes"] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
    ]

    # test system mode update from device
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.OFF

    # test running state update from device
    set_node_attribute(matter_node, 1, 513, 41, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 5)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.HEATING

    set_node_attribute(matter_node, 1, 513, 41, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 6)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 16)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 66)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.COOLING

    set_node_attribute(matter_node, 1, 513, 41, 4)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 32)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 64)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.FAN

    set_node_attribute(matter_node, 1, 513, 41, 128)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["hvac_action"] == HVACAction.OFF

    # change system mode to heat
    set_node_attribute(matter_node, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT

    # change occupied heating setpoint to 20
    set_node_attribute(matter_node, 1, 513, 18, 2000)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["temperature"] == 20


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_thermostat_humidity(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat humidity attribute and state updates."""
    # test entity attributes
    state = hass.states.get("climate.longan_link_hvac")
    assert state

    measured_value = clusters.RelativeHumidityMeasurement.Attributes.MeasuredValue

    # test current humidity update from device
    set_node_attribute(
        matter_node,
        1,
        measured_value.cluster_id,
        measured_value.attribute_id,
        1234,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["current_humidity"] == 12.34

    # test current humidity update from device with zero value
    set_node_attribute(
        matter_node,
        1,
        measured_value.cluster_id,
        measured_value.attribute_id,
        0,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["current_humidity"] == 0.0

    # test current humidity update from device with None value
    set_node_attribute(
        matter_node,
        1,
        measured_value.cluster_id,
        measured_value.attribute_id,
        None,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert "current_humidity" not in state.attributes


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_thermostat_service_calls(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test climate platform service calls."""
    # test single-setpoint temperature adjustment when cool mode is active
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.COOL
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 25,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2500,
    )
    matter_client.write_attribute.reset_mock()

    # ensure that no command is executed when the temperature is the same
    set_node_attribute(matter_node, 1, 513, 17, 2500)
    await trigger_subscription_callback(hass, matter_client)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 25,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 0
    matter_client.write_attribute.reset_mock()

    # test single-setpoint temperature adjustment when heat mode is active
    set_node_attribute(matter_node, 1, 513, 28, 4)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 20,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=2000,
    )
    matter_client.write_attribute.reset_mock()

    # test dual setpoint temperature adjustments when heat_cool mode is active
    set_node_attribute(matter_node, 1, 513, 28, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.state == HVACMode.HEAT_COOL

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "target_temp_low": 10,
            "target_temp_high": 30,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=1000,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=3000,
    )
    matter_client.write_attribute.reset_mock()

    # test changing only target_temp_high when target_temp_low stays the same
    set_node_attribute(matter_node, 1, 513, 18, 1000)
    set_node_attribute(matter_node, 1, 513, 17, 2500)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["target_temp_high"] == 25
    assert state.attributes["target_temp_low"] == 10

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "target_temp_low": 10,  # Same as current
            "target_temp_high": 28,  # Different from current
        },
        blocking=True,
    )

    # Only target_temp_high should be written since target_temp_low hasn't changed
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2800,
    )
    matter_client.write_attribute.reset_mock()

    # test change HAVC mode to heat
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            "entity_id": "climate.longan_link_hvac",
            "hvac_mode": HVACMode.HEAT,
        },
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=4,
    )
    matter_client.send_device_command.reset_mock()

    # change target_temp and hvac_mode in the same call
    matter_client.send_device_command.reset_mock()
    matter_client.write_attribute.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 22,
            "hvac_mode": HVACMode.COOL,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 2
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=3,
    )
    assert matter_client.write_attribute.call_args_list[1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/17",
        value=2200,
    )
    matter_client.write_attribute.reset_mock()


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
async def test_room_airconditioner(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test if a climate entity is created for a Room Airconditioner device."""
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.attributes["current_temperature"] == 20
    # room airconditioner has mains power on OnOff cluster with value set to False
    assert state.state == HVACMode.OFF

    # test supported features correctly parsed
    # WITHOUT temperature_range support
    mask = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF
    assert state.attributes["supported_features"] & mask == mask

    # set mains power to ON (OnOff cluster)
    set_node_attribute(matter_node, 1, 6, 0, True)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")

    # test supported HVAC modes include fan and dry modes
    assert state.attributes["hvac_modes"] == [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT_COOL,
    ]
    # test fan-only hvac mode
    set_node_attribute(matter_node, 1, 513, 28, 7)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.FAN_ONLY

    # test dry hvac mode
    set_node_attribute(matter_node, 1, 513, 28, 8)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state
    assert state.state == HVACMode.DRY

    # test featuremap update
    set_node_attribute(matter_node, 1, 513, 65532, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("climate.room_airconditioner")
    assert state.attributes["supported_features"] & ClimateEntityFeature.TURN_ON


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_eve_thermo_v5_presets(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Eve Thermo v5 thermostat presets attributes and state updates."""
    # test entity attributes
    entity_id = "climate.eve_thermo_20ecd1701"
    state = hass.states.get(entity_id)
    assert state

    # test supported features correctly parsed
    mask = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.PRESET_MODE
    )
    assert state.attributes["supported_features"] & mask == mask

    # Test preset modes parsed correctly from Eve Thermo v5
    # Should use HA standard presets for known ones, original names for others
    # PRESET_NONE is always included to allow users to clear the preset
    assert state.attributes["preset_modes"] == [
        "home",
        "away",
        "sleep",
        "wake",
        "vacation",
        "going_to_sleep",
        "Eco",
        PRESET_NONE,
    ]
    assert state.attributes["preset_mode"] == "home"

    # Get presets from the node for dynamic testing
    presets_attribute = matter_node.endpoints[1].get_attribute_value(
        513,
        clusters.Thermostat.Attributes.Presets.attribute_id,
    )
    preset_by_name = {preset.name: preset.presetHandle for preset in presets_attribute}

    # test set_preset_mode with "home" preset (HA standard)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "home",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(
            presetHandle=preset_by_name["Home"]
        ),
    )
    # Verify preset_mode is optimistically updated
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "home"
    matter_client.send_device_command.reset_mock()

    # test set_preset_mode with "away" preset (HA standard)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "away",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(
            presetHandle=preset_by_name["Away"]
        ),
    )
    # Verify preset_mode is optimistically updated
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "away"
    matter_client.send_device_command.reset_mock()

    # test set_preset_mode with "eco" preset (custom, device-provided name)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "Eco",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(
            presetHandle=preset_by_name["Eco"]
        ),
    )
    matter_client.send_device_command.reset_mock()

    # test set_preset_mode with invalid preset mode
    # The climate platform validates preset modes before calling our method

    # Get current state to derive expected modes
    state = hass.states.get(entity_id)
    assert state
    expected_modes = ", ".join(state.attributes["preset_modes"])

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {
                "entity_id": entity_id,
                "preset_mode": "InvalidPreset",
            },
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_preset_mode"
    assert err.value.translation_placeholders == {
        "mode": "InvalidPreset",
        "modes": expected_modes,
    }

    # Ensure no command was sent for invalid preset
    assert matter_client.send_device_command.call_count == 0
    # Test that preset_mode is updated when ActivePresetHandle is set from device
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
        preset_by_name["Home"],
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "home"

    # Test that preset_mode is updated when ActivePresetHandle changes to different preset
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
        preset_by_name["Away"],
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == "away"

    # Test that preset_mode is PRESET_NONE when ActivePresetHandle is cleared
    set_node_attribute(
        matter_node,
        1,
        513,
        clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
        None,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == PRESET_NONE

    # Test that users can set preset_mode to PRESET_NONE to clear the active preset
    matter_client.send_device_command.reset_mock()
    # First set a preset so we have something to clear
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": "home",
        },
        blocking=True,
    )
    matter_client.send_device_command.reset_mock()

    # Now call set_preset_mode with PRESET_NONE to clear it
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {
            "entity_id": entity_id,
            "preset_mode": PRESET_NONE,
        },
        blocking=True,
    )

    # Verify the command was sent with empty bytes to clear the preset
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(presetHandle=b""),
    )
    # Verify preset_mode is optimistically updated to PRESET_NONE
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == PRESET_NONE


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_hvac_mode_error_on_unsupported_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test HVAC mode error when calling entity method directly with unsupported mode."""
    entity_id = "climate.longan_link_hvac"

    # Get the entity object directly via component using DATA_INSTANCES helper
    component = hass.data.get(DATA_INSTANCES, {}).get(Platform.CLIMATE)
    assert component is not None

    entity = component.get_entity(entity_id)
    assert entity is not None

    # Test calling async_set_hvac_mode directly with an unsupported HVAC mode string
    # We pass a string that's not in HVAC_SYSTEM_MODE_MAP
    with pytest.raises(ValueError, match="Unsupported hvac mode"):
        await entity.async_set_hvac_mode("unsupported_mode")

    # Ensure no command was sent
    assert matter_client.write_attribute.call_count == 0


@pytest.mark.parametrize("node_fixture", ["eve_thermo_v5"])
async def test_preset_mode_with_unnamed_preset(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test preset mode when a preset has no name or empty name.

    This tests the fallback preset naming case where a preset does not have
    a mapped presetScenario and also has no device-provided name, requiring
    the fallback Preset{i} naming pattern.
    """
    entity_id = "climate.eve_thermo_20ecd1701"

    # Get current presets from the node
    presets_attribute = matter_node.endpoints[1].get_attribute_value(
        513,
        clusters.Thermostat.Attributes.Presets.attribute_id,
    )

    # Add a new preset with unmapped scenario (e.g., 255) and no name
    if presets_attribute:
        new_preset = clusters.Thermostat.Structs.PresetStruct(
            presetHandle=b"\xff",
            presetScenario=255,  # Unmapped scenario
            name="",  # Empty name
        )
        presets_attribute.append(new_preset)

        # Update the node with the new preset list
        set_node_attribute(
            matter_node,
            1,
            513,
            clusters.Thermostat.Attributes.Presets.attribute_id,
            presets_attribute,
        )

        # Trigger subscription callback to update entity
        await trigger_subscription_callback(hass, matter_client)

        # Verify the preset was added with the fallback name "Preset8"
        state = hass.states.get(entity_id)
        assert state
        assert "Preset8" in state.attributes["preset_modes"]

        # Test that the unnamed preset can be set as active
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {
                "entity_id": entity_id,
                "preset_mode": "Preset8",
            },
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["preset_mode"] == "Preset8"

        # Test that preset_mode is PRESET_NONE when ActivePresetHandle is cleared
        set_node_attribute(
            matter_node,
            1,
            513,
            clusters.Thermostat.Attributes.ActivePresetHandle.attribute_id,
            None,
        )
        await trigger_subscription_callback(hass, matter_client)
        state = hass.states.get(entity_id)
        assert state
        assert state.attributes["preset_mode"] == PRESET_NONE
