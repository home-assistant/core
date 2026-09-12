"""Test Matter locks."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.errors import MatterError
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
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

from tests.common import mock_restore_cache_with_extra_data

THERMOSTAT_ENTITY_ID = "climate.longan_link_hvac"
ROOM_AC_ENTITY_ID = "climate.room_airconditioner"


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

    # fractional setpoints must round, not truncate: 10.2 * 100 is 1019.9999…
    # in IEEE 754, so int() would produce 1019 instead of 1020.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": "climate.longan_link_hvac",
            "temperature": 10.2,
            "hvac_mode": HVACMode.HEAT,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_args_list[-1] == call(
        node_id=matter_node.node_id,
        attribute_path="1/513/18",
        value=1020,
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

    # Test preset_mode updates when ActivePresetHandle changes
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

    # Verify the command was sent with null value to clear the preset
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Thermostat.Commands.SetActivePresetRequest(presetHandle=None),
    )
    # Verify preset_mode is optimistically updated to PRESET_NONE
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes["preset_mode"] == PRESET_NONE


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

    assert presets_attribute is not None

    # Add a new preset with unmapped scenario (e.g., 255) and no name
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


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
@pytest.mark.parametrize("attributes", [{"1/513/0": None}])
async def test_thermostat_with_null_local_temperature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test thermostat is created when LocalTemperature is null."""
    state = hass.states.get("climate.longan_link_hvac")
    assert state
    assert state.attributes["current_temperature"] is None


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
@pytest.mark.parametrize(
    ("system_mode", "hvac_mode"),
    [
        pytest.param(1, HVACMode.HEAT_COOL, id="auto"),
        pytest.param(3, HVACMode.COOL, id="cool"),
        pytest.param(4, HVACMode.HEAT, id="heat"),
    ],
)
async def test_turn_on_restores_reported_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    system_mode: int,
    hvac_mode: HVACMode,
) -> None:
    """Only turn_on restores the mode reported before an external shutdown."""
    set_node_attribute(matter_node, 1, 513, 28, system_mode)
    await trigger_subscription_callback(hass, matter_client)
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )

    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=system_mode
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == hvac_mode


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
@pytest.mark.parametrize(
    "attributes", [{"1/513/28": 1}, {"1/513/28": 3}, {"1/513/28": 4}]
)
@pytest.mark.usefixtures("matter_node")
async def test_turn_on_keeps_running_mode(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Turning on an already running thermostat does not send commands."""
    initial_state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert initial_state
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == initial_state.state


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_turn_on_after_reload(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """Reload keeps the thermostat off until turn_on restores its previous mode."""
    await hass.services.async_call(
        "climate", "turn_off", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.reset_mock()

    entry = hass.config_entries.async_entries("matter")[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()
    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=3
    )


@pytest.mark.parametrize(
    ("stored_mode", "system_mode", "expected_mode"),
    [
        pytest.param("cool", 0, 3, id="restore-cool"),
        pytest.param("heat", 0, 4, id="restore-heat"),
        pytest.param("heat_cool", 0, 1, id="restore-auto"),
        pytest.param(None, 0, 1, id="no-history"),
        pytest.param("off", 0, 1, id="off-history"),
        pytest.param("invalid", 0, 1, id="invalid-history"),
        pytest.param("fan_only", 0, 1, id="unsupported-history"),
        pytest.param("heat", 3, 3, id="live-mode-takes-precedence"),
    ],
)
async def test_turn_on_restored_history(
    hass: HomeAssistant,
    matter_client: MagicMock,
    stored_mode: str | None,
    system_mode: int,
    expected_mode: int,
) -> None:
    """Stored history never overrides device state or sends commands on setup."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(THERMOSTAT_ENTITY_ID, HVACMode.OFF), {"last_hvac_mode": stored_mode})],
    )
    matter_node = await setup_integration_with_node_fixture(
        hass, "longan_link_thermostat", matter_client, {"1/513/28": system_mode}
    )
    matter_client.write_attribute.assert_not_called()
    matter_client.send_device_command.assert_not_called()

    # An external shutdown must not overwrite the last running mode.
    set_node_attribute(matter_node, 1, 513, 28, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(THERMOSTAT_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.write_attribute.assert_not_called()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=expected_mode
    )


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_turn_on_after_supported_modes_change(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """Fall back when a previously used mode is no longer supported."""
    set_node_attribute(matter_node, 1, 513, 28, 0)
    set_node_attribute(
        matter_node, 1, 513, 65532, clusters.Thermostat.Bitmaps.Feature.kHeating
    )
    await trigger_subscription_callback(hass, matter_client)
    matter_client.write_attribute.assert_not_called()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=4
    )


@pytest.mark.parametrize("node_fixture", ["longan_link_thermostat"])
async def test_explicit_mode_overrides_history(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """An explicit mode command is not replaced by the remembered cooling mode."""
    await hass.services.async_call(
        "climate", "turn_off", {"entity_id": THERMOSTAT_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": THERMOSTAT_ENTITY_ID, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=4
    )


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize("attributes", [{"1/6/0": True, "1/513/28": 4}])
@pytest.mark.parametrize(
    ("hvac_mode", "system_mode"),
    [
        pytest.param(HVACMode.COOL, 3, id="cool"),
        pytest.param(HVACMode.HEAT_COOL, 1, id="auto"),
        pytest.param(HVACMode.DRY, 8, id="dry"),
        pytest.param(HVACMode.FAN_ONLY, 7, id="fan-only"),
    ],
)
async def test_turn_on_uses_mode_selected_with_power_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hvac_mode: HVACMode,
    system_mode: int,
) -> None:
    """An explicit mode selected while power is off replaces the remembered mode."""
    set_node_attribute(matter_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)
    matter_client.write_attribute.assert_not_called()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": ROOM_AC_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=system_mode
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(ROOM_AC_ENTITY_ID)
    assert state
    assert state.state == HVACMode.OFF
    matter_client.send_device_command.assert_not_called()
    matter_client.write_attribute.reset_mock()

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=system_mode
    )
    matter_client.send_device_command.assert_called_once_with(
        node_id=matter_node.node_id, endpoint_id=1, command=clusters.OnOff.Commands.On()
    )


@pytest.mark.parametrize("node_fixture", ["mock_room_airconditioner"])
@pytest.mark.parametrize("attributes", [{"1/6/0": True, "1/513/28": 4}])
async def test_failed_mode_write_keeps_previous_mode(
    hass: HomeAssistant, matter_client: MagicMock, matter_node: MatterNode
) -> None:
    """A failed mode write while power is off does not change the remembered mode."""
    set_node_attribute(matter_node, 1, 6, 0, False)
    await trigger_subscription_callback(hass, matter_client)
    matter_client.write_attribute.side_effect = MatterError("Mode write failed")
    with pytest.raises(HomeAssistantError, match="Mode write failed"):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": ROOM_AC_ENTITY_ID, "hvac_mode": HVACMode.COOL},
            blocking=True,
        )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=3
    )
    matter_client.send_device_command.assert_not_called()
    matter_client.write_attribute.reset_mock(side_effect=True)

    await hass.services.async_call(
        "climate", "turn_on", {"entity_id": ROOM_AC_ENTITY_ID}, blocking=True
    )
    matter_client.write_attribute.assert_called_once_with(
        node_id=matter_node.node_id, attribute_path="1/513/28", value=4
    )
    matter_client.send_device_command.assert_called_once_with(
        node_id=matter_node.node_id, endpoint_id=1, command=clusters.OnOff.Commands.On()
    )
