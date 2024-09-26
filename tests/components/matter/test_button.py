"""Test Matter switches."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest

from homeassistant.core import HomeAssistant

from .common import setup_integration_with_node_fixture


@pytest.fixture(name="powerplug_node")
async def powerplug_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a Powerplug node."""
    return await setup_integration_with_node_fixture(
        hass, "eve_energy_plug", matter_client
    )


@pytest.fixture(name="dishwasher_node")
async def dishwasher_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for an dishwasher node."""
    return await setup_integration_with_node_fixture(
        hass, "silabs_dishwasher", matter_client
    )


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_identify_button(
    hass: HomeAssistant,
    matter_client: MagicMock,
    powerplug_node: MatterNode,
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
        node_id=powerplug_node.node_id,
        endpoint_id=1,
        command=clusters.Identify.Commands.Identify(identifyTime=15),
    )


async def test_operational_state_buttons(
    hass: HomeAssistant,
    matter_client: MagicMock,
    dishwasher_node: MatterNode,
) -> None:
    """Test if button entities are created for operational state commands."""
    assert hass.states.get("button.dishwasher_pause")
    assert hass.states.get("button.dishwasher_start")
    assert hass.states.get("button.dishwasher_stop")

    # resume may not be disocvered as its missing in the supported command list
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
        node_id=dishwasher_node.node_id,
        endpoint_id=1,
        command=clusters.OperationalState.Commands.Pause(),
    )
