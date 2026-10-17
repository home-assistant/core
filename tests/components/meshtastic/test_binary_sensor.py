"""Tests for the Meshtastic binary sensor platform."""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.meshtastic.const import NODE_ONLINE_SECONDS
from homeassistant.components.meshtastic.models import MeshtasticData
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    GATEWAY_ID,
    REMOTE_ID,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

#: Six minutes after the newest timestamp in ``nodes.json``, so every node in
#: the fixture counts as recently heard.
FROZEN_TIME = "2025-09-08T03:06:00+00:00"
#: Thirty seconds before ``!aabbccdd`` (last heard 03:01:20) falls out of the
#: two hour online window.
ALMOST_STALE_TIME = "2025-09-08T05:00:50+00:00"

GATEWAY_CONNECTED = "binary_sensor.ha_gateway_connected"
REMOTE_ONLINE = "binary_sensor.remote_one_online"
REMOTE_VIA_MQTT = "binary_sensor.remote_one_heard_via_mqtt"
SENSOR_NODE_ONLINE = "binary_sensor.weather_shed_online"
SENSOR_NODE_VIA_MQTT = "binary_sensor.weather_shed_heard_via_mqtt"


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Pin the clock so node timestamps are deterministic."""
    freezer.move_to(FROZEN_TIME)


async def _setup_with_nodes(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up the binary sensor platform and push the sample node database."""
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, entry)
    for node in node_fixtures.values():
        await inject_node_info(hass, pubsub, interface, node)


@pytest.mark.usefixtures("mock_meshtastic_client", "entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the binary sensors created for the sample mesh."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_gateway_connectivity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
) -> None:
    """Test that the gateway link state keeps reporting while the link is down."""
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(GATEWAY_CONNECTED))
    assert state.state == STATE_ON

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(GATEWAY_CONNECTED))
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_meshtastic_client", "entity_registry_enabled_by_default")
async def test_node_flags(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the boolean flags reported per node."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(REMOTE_ONLINE))
    assert state.state == STATE_ON
    assert (state := hass.states.get(REMOTE_VIA_MQTT))
    assert state.state == STATE_OFF
    assert (state := hass.states.get(SENSOR_NODE_VIA_MQTT))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_goes_offline_when_it_stops_being_heard(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a node falls out of the online window on its own."""
    freezer.move_to(ALMOST_STALE_TIME)
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )

    assert (state := hass.states.get(REMOTE_ONLINE))
    assert state.state == STATE_ON

    # Nothing pushes "this node went quiet", so the platform has to schedule
    # the transition itself.
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(REMOTE_ONLINE))
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_never_heard_is_offline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a node whose report is already stale never comes up online."""
    node = dict(node_fixtures[REMOTE_ID])
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    freezer.tick(timedelta(seconds=NODE_ONLINE_SECONDS + 60))
    await inject_node_info(hass, mock_pubsub, mock_meshtastic_client, node)

    assert (state := hass.states.get(REMOTE_ONLINE))
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_discovered_at_runtime(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a node heard after setup gets entities without a reload."""
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(REMOTE_ONLINE) is None

    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )

    assert (state := hass.states.get(REMOTE_ONLINE))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_relayed_node_gets_no_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a node that only ever relayed traffic gets no device."""
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_handle_node_updated(
        coordinator.data.nodes[GATEWAY_ID].with_updates(
            num=1, node_id="!00000001", long_name=None, presumptive=True
        )
    )
    await hass.async_block_till_done()

    assert "!00000001" in coordinator.data.nodes
    assert not hass.states.async_entity_ids_count("binary_sensor") - 1


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_forgotten_node_is_reconciled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a node the mesh forgot loses its entities while the link is up."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert entity_registry.async_get(REMOTE_ONLINE) is not None

    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_set_updated_data(
        MeshtasticData(
            gateway=coordinator.gateway,
            nodes={GATEWAY_ID: coordinator.data.nodes[GATEWAY_ID]},
        )
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(REMOTE_ONLINE) is None
    assert entity_registry.async_get(REMOTE_VIA_MQTT) is None
    assert entity_registry.async_get(SENSOR_NODE_ONLINE) is None
    assert hass.states.get(GATEWAY_CONNECTED) is not None


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_no_pruning_while_the_link_is_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that losing the link never removes a node's entities."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert entity_registry.async_get(REMOTE_ONLINE) is not None

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)
    coordinator = mock_config_entry.runtime_data.coordinator
    assert not coordinator.client.connected

    coordinator.async_set_updated_data(
        MeshtasticData(gateway=coordinator.gateway, nodes={})
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(REMOTE_ONLINE) is not None
    assert (state := hass.states.get(REMOTE_ONLINE))
    assert state.state == STATE_UNAVAILABLE
