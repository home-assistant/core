"""Test Matter select entities."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    create_node_from_fixture,
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

from tests.common import MockConfigEntry

@pytest.mark.usefixtures("entity_registry_enabled_by_default", "matter_devices")
async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test selects."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize("node_fixture", ["mock_dimmable_light"])
async def test_mode_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test select entities are created for the ModeSelect cluster attributes."""
    state = hass.states.get("select.mock_dimmable_light_led_color")
    assert state
    assert state.state == "Aqua"
    assert state.attributes["options"] == [
        "Red",
        "Orange",
        "Lemon",
        "Lime",
        "Green",
        "Teal",
        "Cyan",
        "Aqua",
        "Blue",
        "Violet",
        "Magenta",
        "Pink",
        "White",
    ]
    # name should be derived from description attribute
    assert state.attributes["friendly_name"] == "Mock Dimmable Light LED Color"
    set_node_attribute(matter_node, 6, 80, 3, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.mock_dimmable_light_led_color")
    assert state.state == "Orange"
    # test select option
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.mock_dimmable_light_led_color",
            "option": "Lime",
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=6,
        command=clusters.ModeSelect.Commands.ChangeToMode(newMode=3),
    )


@pytest.mark.parametrize("node_fixture", ["mock_dimmable_light"])
async def test_attribute_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test select entities are created for attribute based discovery schema(s)."""
    entity_id = "select.mock_dimmable_light_power_on_behavior_on_startup"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "previous"
    assert state.attributes["options"] == ["on", "off", "toggle", "previous"]
    assert (
        state.attributes["friendly_name"]
        == "Mock Dimmable Light Power-on behavior on startup"
    )
    set_node_attribute(matter_node, 1, 6, 16387, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.state == "on"
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": entity_id,
            "option": "off",
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.OnOff.Attributes.StartUpOnOff,
        ),
        value=0,
    )
    # test that an invalid value (e.g. 253) leads to an unknown state
    set_node_attribute(matter_node, 1, 6, 16387, 253)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("node_fixture", "entity_id", "unique_id"),
    [
        (
            "aqara_door_window_p2",
            "select.aqara_door_and_window_sensor_p2_sensitivity",
            "00000000000004D2-000000000000005B-MatterNodeDevice-1-"
            "AqaraBooleanStateConfigurationCurrentSensitivityLevel-128-0",
        ),
        (
            "aqara_motion_p2",
            "select.aqara_motion_and_light_sensor_p2_sensitivity",
            "00000000000004D2-0000000000000053-MatterNodeDevice-1-"
            "AqaraOccupancySensorBooleanStateConfigurationCurrentSensitivityLevel-128-0",
        ),
        (
            "aqara_presence_fp300",
            "select.presence_multi_sensor_fp300_1_sensitivity",
            "00000000000004D2-00000000000000CD-MatterNodeDevice-1-"
            "AqaraOccupancySensorBooleanStateConfigurationCurrentSensitivityLevel-128-0",
        ),
        (
            "heiman_motion_sensor_m1",
            "select.smart_motion_sensor_sensitivity",
            "00000000000004D2-0000000000000058-MatterNodeDevice-1-"
            "HeimanOccupancySensorBooleanStateConfigurationCurrentSensitivityLevel-128-0",
        ),
    ],
)
async def test_existing_legacy_sensitivity_selects_are_restored(
    hass: HomeAssistant,
    matter_client: MagicMock,
    entity_registry: er.EntityRegistry,
    node_fixture: str,
    entity_id: str,
    unique_id: str,
) -> None:
    """Test existing legacy sensitivity selects are restored for migration."""
    node = create_node_from_fixture(node_fixture)
    matter_client.get_nodes.return_value = [node]
    matter_client.get_node.side_effect = lambda node_id: node

    config_entry = MockConfigEntry(
        domain="matter", data={"url": "http://mock-matter-server-url"}
    )
    config_entry.add_to_hass(hass)

    entry = entity_registry.async_get_or_create(
        "select",
        "matter",
        unique_id,
        config_entry=config_entry,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        original_name="Sensitivity",
        suggested_object_id=entity_id.removeprefix("select."),
        translation_key="sensitivity_level",
    )
    assert entry.entity_id == entity_id

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("node_fixture", ["aqara_door_window_p2"])
async def test_legacy_aqara_door_window_p2_sensitivity_select(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test the legacy Aqara select remains available when explicitly enabled."""
    entity_id = "select.aqara_door_and_window_sensor_p2_sensitivity"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "30 mm"
    assert state.attributes["options"] == ["10 mm", "20 mm", "30 mm"]

    set_node_attribute(matter_node, 1, 128, 0, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "20 mm"


@pytest.mark.parametrize("node_fixture", ["silabs_laundrywasher"])
async def test_list_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test ListSelect entities are discovered and working from a laundrywasher fixture."""
    state = hass.states.get("select.laundrywasher_temperature_level")
    assert state
    assert state.state == "Colors"
    assert state.attributes["options"] == ["Cold", "Colors", "Whites"]
    # Change temperature_level
    set_node_attribute(matter_node, 1, 86, 4, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.laundrywasher_temperature_level")
    assert state.state == "Cold"
    # test select option
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.laundrywasher_temperature_level",
            "option": "Whites",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.TemperatureControl.Commands.SetTemperature(
            targetTemperatureLevel=2
        ),
    )
    # test that an invalid value (e.g. 253) leads to an unknown state
    set_node_attribute(matter_node, 1, 86, 4, 253)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.laundrywasher_temperature_level")
    assert state.state == "unknown"

    # SpinSpeedCurrent
    matter_client.write_attribute.reset_mock()
    state = hass.states.get("select.laundrywasher_spin_speed")
    assert state
    assert state.state == "Off"
    assert state.attributes["options"] == ["Off", "Low", "Medium", "High"]
    set_node_attribute(matter_node, 1, 83, 1, 3)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.laundrywasher_spin_speed")
    assert state.state == "High"
    # test select option
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.laundrywasher_spin_speed",
            "option": "High",
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.LaundryWasherControls.Attributes.SpinSpeedCurrent,
        ),
        value=3,
    )
    # test that an invalid value (e.g. 253) leads to an unknown state
    set_node_attribute(matter_node, 1, 83, 1, 253)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.laundrywasher_spin_speed")
    assert state.state == "unknown"


@pytest.mark.parametrize("node_fixture", ["silabs_laundrywasher"])
async def test_map_select_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test MatterMapSelectEntity entities are discovered and working from a laundrywasher fixture."""
    # NumberOfRinses
    state = hass.states.get("select.laundrywasher_number_of_rinses")
    assert state
    assert state.state == "off"
    assert state.attributes["options"] == ["off", "normal"]
    set_node_attribute(matter_node, 1, 83, 2, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.laundrywasher_number_of_rinses")
    assert state.state == "normal"


@pytest.mark.parametrize("node_fixture", ["mock_pump"])
async def test_pump(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test MatterAttributeSelectEntity entities are discovered and working from a pump fixture."""
    # OperationMode
    state = hass.states.get("select.mock_pump_mode")
    assert state
    assert state.state == "normal"
    assert state.attributes["options"] == ["normal", "minimum", "maximum", "local"]

    set_node_attribute(matter_node, 1, 512, 32, 3)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.mock_pump_mode")
    assert state.state == "local"


@pytest.mark.parametrize("node_fixture", ["mock_microwave_oven"])
async def test_microwave_oven(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test ListSelect entity is discovered and working from a microwave oven fixture."""

    # SupportedWatts    from MicrowaveOvenControl cluster (1/96/6)
    # SelectedWattIndex from MicrowaveOvenControl cluster (1/96/7)
    matter_client.write_attribute.reset_mock()
    state = hass.states.get("select.mock_microwave_oven_power_level_w")
    assert state
    assert state.state == "1000"
    assert state.attributes["options"] == [
        "100",
        "200",
        "300",
        "400",
        "500",
        "600",
        "700",
        "800",
        "900",
        "1000",
    ]

    # test select option
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.mock_microwave_oven_power_level_w",
            "option": "900",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.MicrowaveOvenControl.Commands.SetCookingParameters(
            wattSettingIndex=8
        ),
    )


@pytest.mark.parametrize("node_fixture", ["secuyou_smart_lock"])
async def test_door_lock_operating_mode_select(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Door Lock Operating Mode select entity discovery and interaction.

    Verifies:
    - Options are filtered based on SupportedOperatingModes bitmap
    - Attribute updates reflect current option
    - Selecting an option writes correct enum value
    """
    entity_id = "select.secuyou_smart_lock_operating_mode"
    state = hass.states.get(entity_id)
    assert state, "Missing operating mode select entity"
    # According to the spec, bit=0 means supported and bit=1 means not supported.
    # The fixture bitmap clears bits 0, 2, and 3, so the supported modes are
    # Normal, Privacy, and NoRemoteLockUnlock; the other bits are set (not
    # supported).
    assert set(state.attributes["options"]) == {
        "normal",
        "privacy",
        "no_remote_lock_unlock",
    }
    # Verify that the initial state is part of the allowed options
    assert state.state in state.attributes["options"]

    # Dynamically obtain ids instead of hardcoding
    door_lock_cluster_id = clusters.DoorLock.Attributes.OperatingMode.cluster_id
    operating_mode_attr_id = clusters.DoorLock.Attributes.OperatingMode.attribute_id

    # Change OperatingMode attribute on the node to a supported mode ('privacy')
    set_node_attribute(
        matter_node,
        1,
        door_lock_cluster_id,
        operating_mode_attr_id,
        clusters.DoorLock.Enums.OperatingModeEnum.kPrivacy,
    )
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state.state == "privacy"

    # Select another supported option (NoRemoteLockUnlock) via service to validate mapping
    matter_client.write_attribute.reset_mock()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "no_remote_lock_unlock"},
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=clusters.DoorLock.Attributes.OperatingMode,
        ),
        value=clusters.DoorLock.Enums.OperatingModeEnum.kNoRemoteLockUnlock,
    )
