"""Test Matter select entities."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_selects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test selects."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.SELECT)


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
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


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
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


@pytest.mark.parametrize("node_fixture", ["pump"])
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


@pytest.mark.parametrize("node_fixture", ["microwave_oven"])
async def test_microwave_oven(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test ListSelect entity is discovered and working from a microwave oven fixture."""

    # SupportedWatts    from MicrowaveOvenControl cluster (1/96/6)
    # SelectedWattIndex from MicrowaveOvenControl cluster (1/96/7)
    matter_client.write_attribute.reset_mock()
    state = hass.states.get("select.microwave_oven_power_level_w")
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
            "entity_id": "select.microwave_oven_power_level_w",
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


@pytest.mark.parametrize("node_fixture", ["aqara_door_window_p2"])
async def test_aqara_door_window_p2(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test select entity for Aqara contact sensor fixture."""
    # SensitivityLevel attribute
    state = hass.states.get("select.aqara_door_and_window_sensor_p2_sensitivity")
    assert state
    assert state.state == "30 mm"
    assert state.attributes["options"] == ["10 mm", "20 mm", "30 mm"]

    # Change SensitivityLevel to 20 mm
    set_node_attribute(matter_node, 1, 128, 0, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("select.aqara_door_and_window_sensor_p2_sensitivity")
    assert state.state == "20 mm"
