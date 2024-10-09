"""Test Matter number entities."""

from unittest.mock import MagicMock, call

from matter_server.client.models.node import MatterNode
from matter_server.common import custom_clusters
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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
