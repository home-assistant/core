"""Test Matter sensors."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    STATE_OFF,
    WaterHeaterEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)


@pytest.mark.usefixtures("matter_devices")
async def test_water_heaters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test water heaters."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.WATER_HEATER)


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water heater entity."""
    state = hass.states.get("water_heater.water_heater")
    assert state
    assert state.attributes["min_temp"] == 40
    assert state.attributes["max_temp"] == 65
    assert state.attributes["temperature"] == 65
    assert state.attributes["operation_list"] == ["eco", "high_demand", "off"]
    assert state.state == STATE_ECO

    # test supported features correctly parsed
    mask = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.ON_OFF
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    assert state.attributes["supported_features"] & mask == mask


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_set_temperature(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water_heater set temperature service."""
    # test single-setpoint temperature adjustment when eco mode is active
    state = hass.states.get("water_heater.water_heater")

    assert state
    assert state.state == STATE_ECO
    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {
            "entity_id": "water_heater.water_heater",
            "temperature": 52,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path="2/513/18",
        value=5200,
    )
    matter_client.write_attribute.reset_mock()


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
@pytest.mark.parametrize(
    ("operation_mode", "matter_attribute_value"),
    [(STATE_OFF, 0), (STATE_ECO, 4), (STATE_HIGH_DEMAND, 4)],
)
async def test_water_heater_set_operation_mode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    operation_mode: str,
    matter_attribute_value: int,
) -> None:
    """Test water_heater set operation mode service."""
    state = hass.states.get("water_heater.water_heater")
    assert state

    # test change mode to each operation_mode
    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {
            "entity_id": "water_heater.water_heater",
            "operation_mode": operation_mode,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=2,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=matter_attribute_value,
    )


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_boostmode(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water_heater set operation mode service."""
    # Boost 1h (3600s)
    boost_info: type[
        clusters.WaterHeaterManagement.Structs.WaterHeaterBoostInfoStruct
    ] = clusters.WaterHeaterManagement.Structs.WaterHeaterBoostInfoStruct(duration=3600)
    state = hass.states.get("water_heater.water_heater")
    assert state

    # enable water_heater boostmode
    await hass.services.async_call(
        "water_heater",
        "set_operation_mode",
        {
            "entity_id": "water_heater.water_heater",
            "operation_mode": STATE_HIGH_DEMAND,
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=2,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=4,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=2,
        command=clusters.WaterHeaterManagement.Commands.Boost(boostInfo=boost_info),
    )


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_update_from_water_heater(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test enable boost from water heater device side."""
    entity_id = "water_heater.water_heater"

    # confirm initial BoostState (as stored in the fixture)
    state = hass.states.get(entity_id)
    assert state

    # confirm thermostat state is 'high_demand' by setting the BoostState to 1
    set_node_attribute(matter_node, 2, 148, 5, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_HIGH_DEMAND

    # confirm thermostat state is 'eco' by setting the BoostState to 0
    set_node_attribute(matter_node, 2, 148, 5, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ECO


@pytest.mark.parametrize("node_fixture", ["silabs_water_heater"])
async def test_water_heater_turn_on_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test water_heater set turn_off/turn_on."""
    state = hass.states.get("water_heater.water_heater")
    assert state

    # turn_off water_heater
    await hass.services.async_call(
        "water_heater",
        "turn_off",
        {
            "entity_id": "water_heater.water_heater",
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=2,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=0,
    )

    matter_client.write_attribute.reset_mock()

    # turn_on water_heater
    await hass.services.async_call(
        "water_heater",
        "turn_on",
        {
            "entity_id": "water_heater.water_heater",
        },
        blocking=True,
    )
    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=2,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        ),
        value=4,
    )
