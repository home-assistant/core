"""Test Matter number entities."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common import custom_clusters
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_numbers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test numbers."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.NUMBER)


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_level_control_config_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test number entities are created for the LevelControl cluster (config) attributes."""
    state = hass.states.get("number.mock_dimmable_light_on_level")
    assert state
    assert state.state == "255"

    state = hass.states.get("number.mock_dimmable_light_on_transition_time")
    assert state
    assert state.state == "0.0"

    state = hass.states.get("number.mock_dimmable_light_off_transition_time")
    assert state
    assert state.state == "0.0"

    state = hass.states.get("number.mock_dimmable_light_on_off_transition_time")
    assert state
    assert state.state == "0.0"

    set_node_attribute(matter_node, 1, 0x00000008, 0x0011, 20)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("number.mock_dimmable_light_on_level")
    assert state
    assert state.state == "20"


@pytest.mark.parametrize("node_fixture", ["eve_weather_sensor"])
async def test_eve_weather_sensor_altitude(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test weather sensor created from (Eve) custom cluster."""
    # pressure sensor on Eve custom cluster
    state = hass.states.get("number.eve_weather_altitude_above_sea_level")
    assert state
    assert state.state == "40.0"

    set_node_attribute(matter_node, 1, 319486977, 319422483, 800)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.eve_weather_altitude_above_sea_level")
    assert state
    assert state.state == "800.0"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.eve_weather_altitude_above_sea_level",
            "value": 500,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args_list[0] == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=custom_clusters.EveCluster.Attributes.Altitude,
        ),
        value=500,
    )


@pytest.mark.parametrize("node_fixture", ["silabs_refrigerator"])
async def test_temperature_control_temperature_setpoint(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test TemperatureSetpoint from TemperatureControl."""
    # TemperatureSetpoint
    state = hass.states.get("number.refrigerator_temperature_setpoint_2")
    assert state
    assert state.state == "-18.0"

    set_node_attribute(matter_node, 2, 86, 0, -1600)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.refrigerator_temperature_setpoint_2")
    assert state
    assert state.state == "-16.0"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.refrigerator_temperature_setpoint_2",
            "value": -17,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=2,
        command=clusters.TemperatureControl.Commands.SetTemperature(
            targetTemperature=-1700
        ),
    )


@pytest.mark.parametrize("node_fixture", ["dimmable_light"])
async def test_matter_exception_on_write_attribute(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test if a MatterError gets converted to HomeAssistantError by using a dimmable_light fixture."""
    state = hass.states.get("number.mock_dimmable_light_on_level")
    assert state
    matter_client.write_attribute.side_effect = MatterError("Boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.mock_dimmable_light_on_level",
                "value": 500,
            },
            blocking=True,
        )


@pytest.mark.parametrize("node_fixture", ["pump"])
async def test_pump_level(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test level control for pump."""
    # CurrentLevel on LevelControl cluster
    state = hass.states.get("number.mock_pump_setpoint")
    assert state
    assert state.state == "127.0"

    set_node_attribute(matter_node, 1, 8, 0, 100)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get("number.mock_pump_setpoint")
    assert state
    assert state.state == "50.0"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.mock_pump_setpoint",
            "value": 75,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert (
        matter_client.send_device_command.call_args
        == call(
            node_id=matter_node.node_id,
            endpoint_id=1,
            command=clusters.LevelControl.Commands.MoveToLevel(
                level=150
            ),  # 75 * 2 = 150, as the value is multiplied by 2 in the HA to native value conversion
        )
    )


@pytest.mark.parametrize("node_fixture", ["microwave_oven"])
async def test_microwave_oven(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test Cooktime for microwave oven."""

    # Cooktime on MicrowaveOvenControl cluster (1/96/2)
    state = hass.states.get("number.microwave_oven_cook_time")
    assert state
    assert state.state == "30"

    # test set value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": "number.microwave_oven_cook_time",
            "value": 60,  # 60 seconds
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.MicrowaveOvenControl.Commands.SetCookingParameters(
            cookTime=60,  # 60 seconds
        ),
    )
