"""Test Matter switches."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
from matter_server.common.custom_clusters import HeimanCluster
import pytest
from syrupy.assertion import SnapshotAssertion

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


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
async def test_heiman_temporary_mute_button(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test button entity for Heiman SmokeCoAlarm temporary mute request."""
    state = hass.states.get("button.smoke_sensor_temporary_mute")
    assert state
    assert state.attributes["friendly_name"] == "Smoke sensor Temporary mute"
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.smoke_sensor_temporary_mute"},
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=HeimanCluster.Commands.MutingSensor(),
    )


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
@pytest.mark.parametrize("attributes", [{"1/302775297/65529": []}])
@pytest.mark.usefixtures("matter_node")
async def test_heiman_temporary_mute_button_not_discovered_without_muting_command(
    hass: HomeAssistant,
) -> None:
    """Test that the temporary mute button is not created when MutingSensor is absent from AcceptedCommandList."""
    assert hass.states.get("button.smoke_sensor_temporary_mute") is None


@pytest.mark.parametrize("node_fixture", ["heiman_smoke_detector"])
async def test_smoke_detector_self_test(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test button entity is created for a Matter SmokeCoAlarm Cluster."""
    state = hass.states.get("button.smoke_sensor_self_test")
    assert state
    assert state.attributes["friendly_name"] == "Smoke sensor Self-test"
    # test press action
    await hass.services.async_call(
        "button",
        "press",
        {
            "entity_id": "button.smoke_sensor_self_test",
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.SmokeCoAlarm.Commands.SelfTestRequest(),
    )
