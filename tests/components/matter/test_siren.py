"""Test Matter siren entities."""

from unittest.mock import MagicMock, call

from matter_server.client.models.node import MatterNode
from matter_server.common.custom_clusters import HeimanCluster
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
async def test_sirens(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sirens."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.SIREN)


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
async def test_turn_on(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test turning on the siren."""
    state = hass.states.get("siren.smoke_sensor_siren")
    assert state
    assert state.state == "on"

    set_node_attribute(
        matter_node,
        1,
        HeimanCluster.id,
        HeimanCluster.Attributes.SirenActive.attribute_id,
        0,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("siren.smoke_sensor_siren")
    assert state
    assert state.state == "off"

    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": "siren.smoke_sensor_siren"},
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=HeimanCluster.Attributes.SirenActive,
        ),
        value=1,
    )


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
async def test_turn_off(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test turning off the siren."""
    state = hass.states.get("siren.smoke_sensor_siren")
    assert state
    assert state.state == "on"

    await hass.services.async_call(
        "siren",
        "turn_off",
        {"entity_id": "siren.smoke_sensor_siren"},
        blocking=True,
    )

    assert matter_client.write_attribute.call_count == 1
    assert matter_client.write_attribute.call_args == call(
        node_id=matter_node.node_id,
        attribute_path=create_attribute_path_from_attribute(
            endpoint_id=1,
            attribute=HeimanCluster.Attributes.SirenActive,
        ),
        value=0,
    )


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
async def test_unknown_state(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that a None attribute value results in an unknown state."""
    set_node_attribute(
        matter_node,
        1,
        HeimanCluster.id,
        HeimanCluster.Attributes.SirenActive.attribute_id,
        None,
    )
    await trigger_subscription_callback(hass, matter_client)

    state = hass.states.get("siren.smoke_sensor_siren")
    assert state
    assert state.state == "unknown"
