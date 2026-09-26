"""Tests for the Meshtastic device tracker platform."""

from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SourceType,
)
from homeassistant.components.meshtastic.const import (
    CONF_TRACK_POSITION,
    STORAGE_KEY_FORMAT,
)
from homeassistant.components.meshtastic.models import (
    MeshtasticData,
    MeshtasticNode,
    Position,
    PositionSource,
)
from homeassistant.const import (
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    GATEWAY_ID,
    REMOTE_ID,
    REMOTE_NUM,
    SENSOR_NODE_ID,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, snapshot_platform

#: Six minutes after the newest timestamp in ``nodes.json``, so every node in
#: the fixture counts as recently heard.
FROZEN_TIME = "2025-09-08T03:06:00+00:00"

GATEWAY_TRACKER = "device_tracker.ha_gateway_position"
REMOTE_TRACKER = "device_tracker.remote_one_position"
SENSOR_NODE_TRACKER = "device_tracker.weather_shed_position"
#: What a user who renamed a tracker and pointed automations at it would have.
RENAMED_TRACKER = "device_tracker.alice"


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
    """Set up the tracker platform and push the sample node database."""
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await setup_integration(hass, entry)
    for node in node_fixtures.values():
        await inject_node_info(hass, pubsub, interface, node)


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the trackers created for the sample mesh."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_position_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test coordinates, accuracy and the extra attributes of a node."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(REMOTE_TRACKER))
    assert state.state == STATE_NOT_HOME
    assert state.attributes["latitude"] == pytest.approx(52.1111111)
    assert state.attributes["longitude"] == pytest.approx(13.1111111)
    assert state.attributes["source_type"] is SourceType.GPS
    assert state.attributes["altitude"] == 42
    # This position came from the gateway's node database, and
    # ``ConvertToNodeInfo`` copies the coordinates, the altitude, the location
    # source and the time out of ``NodeInfoLite`` and nothing else.  There is
    # no blur radius to report until the node broadcasts a position itself.
    assert state.attributes["gps_accuracy"] == 0
    assert state.attributes["precision_bits"] is None

    # The gateway reported a manual position, which carries no precision bits.
    assert (state := hass.states.get(GATEWAY_TRACKER))
    assert state.attributes["gps_accuracy"] == 0
    assert state.attributes["location_source"] == "LOC_MANUAL"


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_without_position_has_no_tracker(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a node that never reported a position gets no tracker."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert hass.states.get(SENSOR_NODE_TRACKER) is None


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_tracker_added_when_position_arrives(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that a node discovered at runtime gets a tracker without a reload."""
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(REMOTE_TRACKER) is None

    # The node introduces itself first; it has no position yet, so no tracker.
    node = dict(node_fixtures[REMOTE_ID])
    node.pop("position")
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, node | {"position": {}}
    )
    assert hass.states.get(REMOTE_TRACKER) is None

    # ...and the tracker appears as soon as it reports where it is.
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )

    assert (state := hass.states.get(REMOTE_TRACKER))
    assert state.state == STATE_NOT_HOME


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_position_restored_from_node_registry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test that a stored position is available before the mesh says anything.

    ``TrackerEntity`` is not a ``RestoreEntity``, so the persisted node table is
    the only thing that can bring a position back over a restart.
    """
    stored = MeshtasticNode(
        num=REMOTE_NUM,
        node_id=REMOTE_ID,
        long_name="Remote One",
        short_name="RM1",
        hardware_model="HELTEC_V3",
        presumptive=False,
        position=Position(
            latitude=52.5,
            longitude=13.5,
            altitude=17,
            precision_bits=32,
            location_source="LOC_INTERNAL",
            source=PositionSource.NODE_INFO,
        ),
    )
    key = STORAGE_KEY_FORMAT.format(entry_id=mock_config_entry.entry_id)
    hass_storage[key] = {
        "version": 1,
        "minor_version": 1,
        "key": key,
        "data": {"nodes": {REMOTE_ID: stored.as_dict()}},
    }

    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(REMOTE_TRACKER))
    assert state.attributes["latitude"] == pytest.approx(52.5)
    assert state.attributes["longitude"] == pytest.approx(13.5)
    # 32 precision bits is full precision, which reports no radius at all.
    assert state.attributes["gps_accuracy"] == 0


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_tracking_disabled_by_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the option keeps every tracker out of the state machine."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TRACK_POSITION: False}
    )

    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(GATEWAY_TRACKER) is None
    assert not [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if entity.domain == DEVICE_TRACKER_DOMAIN
    ]


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_disabling_the_option_keeps_the_registry_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that unticking the option does not destroy the user's trackers.

    The option lives in an ``OptionsFlowWithReload``, so it takes effect the
    moment it is saved.  Removing the registry entries there would take the
    entity ids, names and areas the user gave them with it, and every
    automation, script and dashboard card that names one would break on a
    toggle - silently, and for good.
    """
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    entity_registry.async_update_entity(REMOTE_TRACKER, new_entity_id=RENAMED_TRACKER)
    assert entity_registry.async_get(RENAMED_TRACKER) is not None

    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TRACK_POSITION: False}
    )
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entry = entity_registry.async_get(RENAMED_TRACKER)
    assert entry is not None
    # Nothing backs it while tracking is off, so it reads as restored.
    assert (state := hass.states.get(RENAMED_TRACKER))
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes["restored"] is True

    # Ticking it again brings that same entity back, not a new one beside it.
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TRACK_POSITION: True}
    )
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, node_fixtures[REMOTE_ID]
    )

    assert entity_registry.async_get(RENAMED_TRACKER) is entry
    assert (state := hass.states.get(RENAMED_TRACKER))
    assert state.state == STATE_NOT_HOME
    assert hass.states.get(REMOTE_TRACKER) is None


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_a_node_database_push_does_not_sharpen_a_blurred_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    packet_fixtures: dict[str, dict[str, Any]],
) -> None:
    """Test that the gateway's own record does not drop the blur radius.

    Every connect and every ``meshtastic.refresh_nodes`` replays the node
    database, and the record the firmware keeps carries no ``precisionBits``:
    ``ConvertToNodeInfo`` copies the coordinates, the altitude, the location
    source and the time, and nothing else.  Applying it over the position the
    node broadcast would turn a deliberate 728 m cell into a full precision
    fix, and flip it back on the node's next broadcast.
    """
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await setup_integration(hass, mock_config_entry)
    # The node introduces itself, then broadcasts where it is.
    known = {k: v for k, v in node_fixtures[REMOTE_ID].items() if k != "position"}
    await inject_node_info(hass, mock_pubsub, mock_meshtastic_client, known)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, packet_fixtures["packet_position"]
    )

    assert (state := hass.states.get(REMOTE_TRACKER))
    assert state.attributes["gps_accuracy"] == 364
    assert state.attributes["precision_bits"] == 16

    # The gateway pushes its record of that very fix: same time, no blur.
    record = dict(node_fixtures[REMOTE_ID])
    record["position"] = {
        key: value
        for key, value in record["position"].items()
        if key != "precisionBits"
    }
    await inject_node_info(hass, mock_pubsub, mock_meshtastic_client, record)

    assert (state := hass.states.get(REMOTE_TRACKER))
    assert state.attributes["gps_accuracy"] == 364
    assert state.attributes["precision_bits"] == 16


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_forgotten_node_is_reconciled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that a node the mesh forgot loses its tracker while the link is up."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert entity_registry.async_get(REMOTE_TRACKER) is not None

    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_set_updated_data(
        MeshtasticData(
            gateway=coordinator.gateway,
            nodes={GATEWAY_ID: coordinator.data.nodes[GATEWAY_ID]},
        )
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(REMOTE_TRACKER) is None
    assert hass.states.get(GATEWAY_TRACKER) is not None


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_no_pruning_while_the_link_is_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that losing the link never removes a tracker."""
    await _setup_with_nodes(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert entity_registry.async_get(REMOTE_TRACKER) is not None

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)
    coordinator = mock_config_entry.runtime_data.coordinator
    assert not coordinator.client.connected

    coordinator.async_set_updated_data(
        MeshtasticData(gateway=coordinator.gateway, nodes={})
    )
    await hass.async_block_till_done()

    assert entity_registry.async_get(REMOTE_TRACKER) is not None
    assert (state := hass.states.get(REMOTE_TRACKER))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_gateway_without_position_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the gateway tracker only appears once it knows where it is."""
    # The node streams its own NodeInfo during the handshake; make that one a
    # node that has never had a fix, so there is nothing to place yet.
    gateway = dict(node_fixtures[GATEWAY_ID])
    node_fixtures[GATEWAY_ID].pop("position", None)
    with patch(
        "homeassistant.components.meshtastic.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get(GATEWAY_TRACKER) is None

    await inject_node_info(hass, mock_pubsub, mock_meshtastic_client, gateway)

    assert (state := hass.states.get(GATEWAY_TRACKER))
    assert state.state != STATE_UNKNOWN
    assert SENSOR_NODE_ID not in state.attributes
