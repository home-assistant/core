"""Test Matter switches."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import snapshot_matter_entities


@pytest.mark.usefixtures("matter_devices")
async def test_buttons(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test buttons."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.BUTTON)


@pytest.mark.parametrize("node_fixture", ["eve_energy_plug"])
async def test_identify_button(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test button entity is created for a Matter Identify Cluster."""
    state = hass.states.get("button.eve_energy_plug_identify")
    assert state
    assert state.attributes["friendly_name"] == "Eve Energy Plug Identify"
    # test press action
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.eve_energy_plug_identify",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.Identify.Commands.Identify(identifyTime=15),
    )


@pytest.mark.parametrize("node_fixture", ["silabs_dishwasher"])
async def test_operational_state_buttons(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test if button entities are created for operational state commands."""
    assert hass.states.get("button.dishwasher_pause")
    assert hass.states.get("button.dishwasher_start")
    assert hass.states.get("button.dishwasher_stop")

    # resume may not be discovered as it's missing in the supported command list
    assert hass.states.get("button.dishwasher_resume") is None

    # test press action
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.dishwasher_pause",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.OperationalState.Commands.Pause(),
    )
