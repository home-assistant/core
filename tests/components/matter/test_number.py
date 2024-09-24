"""Test Matter number entities."""

from unittest.mock import MagicMock, call

from matter_server.client.models.node import MatterNode
from matter_server.common import custom_clusters
from matter_server.common.helpers.util import create_attribute_path_from_attribute
import pytest

from homeassistant.core import HomeAssistant

from .common import (
    set_node_attribute,
    setup_integration_with_node_fixture,
    trigger_subscription_callback,
)


@pytest.fixture(name="light_node")
async def dimmable_light_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a flow sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "dimmable-light", matter_client
    )


@pytest.fixture(name="eve_weather_sensor_node")
async def eve_weather_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a Eve Weather sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "eve-weather-sensor", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_level_control_config_entities(
    hass: HomeAssistant,
    matter_client: MagicMock,
    light_node: MatterNode,
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

    set_node_attribute(light_node, 1, 0x00000008, 0x0011, 20)
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("number.mock_dimmable_light_on_level")
    assert state
    assert state.state == "20"


async def test_eve_weather_sensor_altitude(
    hass: HomeAssistant,
    matter_client: MagicMock,
    eve_weather_sensor_node: MatterNode,
) -> None:
    """Test weather sensor created from (Eve) custom cluster."""
    # pressure sensor on Eve custom cluster
    state = hass.states.get("number.eve_weather_altitude_above_sea_level")
    assert state
    assert state.state == "40.0"

    set_node_attribute(eve_weather_sensor_node, 1, 319486977, 319422483, 800)
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
        node_id=eve_weather_sensor_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=custom_clusters.EveCluster.Attributes.Altitude,
        ),
        value=500,
    )
