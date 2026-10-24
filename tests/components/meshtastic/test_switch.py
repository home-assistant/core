"""Tests for the Meshtastic switch platform.

Every switch here writes to the radio, so the tests drive the whole round
trip: the write is started as a task, the routing packet the firmware answers
with is injected by hand, and only then is the state read back.

The gateway switches are also checked against the firmware's reboot matrix
(``AdminModule::handleSetConfig``, firmware ``v2.7.26.54e0d8d``): a setting
that would make the node restart must never reach an entity, and asking the
shared snapshot to write one has to be refused.
"""

import asyncio
from datetime import timedelta
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from meshtastic.protobuf import admin_pb2, config_pb2, mesh_pb2
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.meshtastic.client import MeshtasticConnectionError
from homeassistant.components.meshtastic.config_entity import (
    LIVE_FIELDS,
    REBOOTING_FIELDS,
    SECTION_DEVICE,
    SECTION_LORA,
    async_get_config_snapshot,
)
from homeassistant.components.meshtastic.const import DOMAIN, RECONNECT_MAX_DELAY
from homeassistant.components.meshtastic.switch import GATEWAY_SWITCHES, NODE_SWITCHES
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    REMOTE_NUM,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    inject_packet,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

# Six minutes after the newest timestamp in ``nodes.json``.
FROZEN_TIME = "2025-09-08 03:06:00+00:00"

#: The packet id the library assigns to the admin message a write produces.
ADMIN_PACKET_ID = 222333444
#: A packet id belonging to somebody else's send, to prove the write does not
#: correlate on the library's shared counter.
OTHER_PACKET_ID = 555666777

TX_ENABLED = "switch.ha_gateway_transmitter_enabled"
IGNORE_MQTT = "switch.ha_gateway_ignore_mqtt_traffic"
CONFIG_OK_TO_MQTT = "switch.ha_gateway_allow_configuration_over_mqtt"
LED_HEARTBEAT = "switch.ha_gateway_led_heartbeat_disabled"
REMOTE_FAVORITE = "switch.remote_one_favorite"
REMOTE_IGNORED = "switch.remote_one_ignored"

#: One entity from each of the other three platforms that read the same
#: configuration snapshot the switches do.
HOP_LIMIT = "number.ha_gateway_hop_limit"
BUZZER_MODE = "select.ha_gateway_buzzer_mode"
TZDEF = "text.ha_gateway_time_zone"

#: Every platform that asks for the shared configuration snapshot.
CONFIG_PLATFORMS = [Platform.NUMBER, Platform.SELECT, Platform.SWITCH, Platform.TEXT]

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


@pytest.fixture(autouse=True)
def node_configuration(gateway_local_node: SimpleNamespace) -> None:
    """Give the node the configuration a real gateway would report.

    ``tx_power`` and ``channel_num`` are deliberately non-default: they are on
    the rebooting side of the LoRa list, so a write that lost them would make
    the firmware restart the node.  Every write test asserts they came back.
    """
    lora = gateway_local_node.localConfig.lora
    lora.tx_enabled = True
    lora.ignore_mqtt = True
    lora.tx_power = 27
    lora.channel_num = 20
    gateway_local_node.localConfig.device.node_info_broadcast_secs = 10800


@pytest.fixture
def admin_writes(mock_meshtastic_client: MagicMock) -> list[admin_pb2.AdminMessage]:
    """Record the admin message every configuration write hands the library.

    ``meshtastic.node.Node.writeConfig()`` copies the whole section out of the
    configuration the node reported, sends it and returns nothing, leaving the
    id of the packet it framed on the interface.  The stand-in does the same,
    so the recorded message is exactly what would go on the wire.
    """
    local_node = mock_meshtastic_client.localNode
    sent: list[admin_pb2.AdminMessage] = []

    def _write_config(name: str) -> None:
        message = admin_pb2.AdminMessage()
        getattr(message.set_config, name).CopyFrom(
            getattr(local_node.localConfig, name)
        )
        sent.append(message)
        # ``MeshtasticInterface`` records the id of every packet it frames,
        # which is where the write reads back the id of the one it just sent.
        mock_meshtastic_client.last_packet_id = ADMIN_PACKET_ID

    local_node.writeConfig = MagicMock(side_effect=_write_config)
    for method in ("setFavorite", "removeFavorite", "setIgnored", "removeIgnored"):
        setattr(
            local_node,
            method,
            MagicMock(return_value=mesh_pb2.MeshPacket(id=ADMIN_PACKET_ID)),
        )
    mock_meshtastic_client.last_packet_id = 0
    return sent


def routing_packet(request_id: int, error: str = "NONE") -> dict[str, Any]:
    """Return the routing packet the gateway answers an admin message with."""
    return {
        "from": GATEWAY_NUM,
        "to": GATEWAY_NUM,
        "fromId": GATEWAY_ID,
        "toId": GATEWAY_ID,
        "channel": 0,
        "id": 987654330,
        "rxTime": 1757300600,
        "priority": "ACK",
        "decoded": {
            "portnum": "ROUTING_APP",
            "requestId": request_id,
            "routing": {"errorReason": error},
        },
    }


async def setup_switch_platform(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up only the switch platform, with one known mesh node."""
    with patch("homeassistant.components.meshtastic.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, entry)
    await inject_node_info(hass, pubsub, interface, node_fixtures[REMOTE_ID])


async def start_call(
    hass: HomeAssistant, service: str, entity_id: str
) -> asyncio.Task[None]:
    """Start a switch action and let it reach the radio."""
    task = hass.async_create_task(
        hass.services.async_call(
            SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    )
    # The library call runs in the executor; give it a few loop iterations to
    # get out before the node's answer is injected.
    for _ in range(10):
        await asyncio.sleep(0)
    return task


async def settle(hass: HomeAssistant) -> None:
    """Let the client's background tasks make progress.

    The reconnect supervisor is a background task, which
    ``async_block_till_done`` deliberately does not wait for.
    """
    for _ in range(5):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


async def reconnect(hass: HomeAssistant) -> None:
    """Wait out the reconnect backoff, whatever step it has reached."""
    await settle(hass)
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECONNECT_MAX_DELAY + 1)
    )
    await settle(hass)


def errors(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the error records, minus the coordinator's own link failure.

    ``async_set_update_error`` logs a lost link once, at error level.  That is
    the update coordinator reporting the very thing a test arranges, not the
    configuration read failing.
    """
    return [
        record
        for record in caplog.records
        if record.levelno >= logging.ERROR
        and not record.getMessage().startswith("Error requesting meshtastic data")
    ]


class LocalNodeThatLosesTheLink:
    """A ``localNode`` whose configuration is unreadable after the handshake.

    ``build_gateway_info`` reads it once while connecting; every read after
    that raises the ``OSError`` a socket that has gone away produces, which is
    what the platforms run into when the node drops the link in the window
    between the connectivity check and the forwarding of the platforms.
    """

    def __init__(self, local_node: SimpleNamespace) -> None:
        """Wrap the node stand-in the fixtures built."""
        self._local_node = local_node
        self.reads = 0

    def __getattr__(self, name: str) -> Any:
        """Answer everything else as the wrapped node would."""
        return getattr(self._local_node, name)

    @property
    def localConfig(self) -> Any:
        """Return the downloaded configuration, until the link is gone."""
        self.reads += 1
        if self.reads > 1:
            raise OSError("Connection reset by peer")
        return self._local_node.localConfig


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the switches created for the gateway and one mesh node."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_state_comes_from_the_downloaded_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that each switch shows what the node reported on connect."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(TX_ENABLED))
    assert state.state == STATE_ON
    assert (state := hass.states.get(IGNORE_MQTT))
    assert state.state == STATE_ON
    assert (state := hass.states.get(CONFIG_OK_TO_MQTT))
    assert state.state == STATE_OFF
    assert (state := hass.states.get(LED_HEARTBEAT))
    assert state.state == STATE_OFF
    # Reading the configuration is a local call into the library, so nothing
    # was put on the mesh to learn any of this.
    mock_meshtastic_client.sendData.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_on_sends_the_whole_section_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test the exact admin payload one flipped switch produces.

    ``handleSetConfig`` replaces its whole ``Config.LoRaConfig`` with the one
    it receives and compares the rebooting fields against the old copy, so the
    write has to start from the section the node reported and change only the
    one field.  A dropped ``tx_power`` or ``channel_num`` here would restart
    the node.
    """
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_call(hass, SERVICE_TURN_ON, CONFIG_OK_TO_MQTT)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.writeConfig.assert_called_once_with(SECTION_LORA)
    assert len(admin_writes) == 1
    assert admin_writes[0].set_config.lora == config_pb2.Config.LoRaConfig(
        region=config_pb2.Config.LoRaConfig.RegionCode.EU_868,
        modem_preset=config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST,
        hop_limit=3,
        tx_enabled=True,
        ignore_mqtt=True,
        tx_power=27,
        channel_num=20,
        config_ok_to_mqtt=True,
    )
    assert (state := hass.states.get(CONFIG_OK_TO_MQTT))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_device_switch_writes_only_the_device_section(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that a device switch touches the device section and nothing else."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_call(hass, SERVICE_TURN_ON, LED_HEARTBEAT)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.writeConfig.assert_called_once_with(SECTION_DEVICE)
    assert admin_writes[0].set_config.device == config_pb2.Config.DeviceConfig(
        role=config_pb2.Config.DeviceConfig.Role.CLIENT,
        node_info_broadcast_secs=10800,
        led_heartbeat_disabled=True,
    )
    assert admin_writes[0].set_config.WhichOneof("payload_variant") == "device"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "admin_writes")
async def test_a_write_correlates_on_the_packet_it_sent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that another sender's packet id is never taken for this write's.

    ``Node.writeConfig()`` sends the ``AdminMessage`` and returns nothing, so
    the id the node's answer will quote has to come from the interface.
    ``MeshInterface.currentPacketId`` is not that id: ``_generatePacketId()``
    advances the same counter for every caller on every thread, so a write that
    correlates on it waits out the whole ``ADMIN_LOCAL_SET`` deadline and is
    reported as ``timeout_no_ack`` even though the node applied it.
    ``MeshtasticInterface`` records the packet it actually framed instead.
    """
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    # Somebody else's send moves the library's shared counter on between the
    # write and the read: the heartbeat timer, another entity, the CLI.
    mock_meshtastic_client.currentPacketId = OTHER_PACKET_ID

    task = await start_call(hass, SERVICE_TURN_ON, CONFIG_OK_TO_MQTT)
    assert mock_meshtastic_client.currentPacketId == OTHER_PACKET_ID
    # The node acknowledges the packet the write framed.
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    # The other sender's packet is answered too, and its answer is a failure.
    # It belongs to a packet this entity never sent, so it is an orphan and the
    # write that has already succeeded must not notice it.
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        routing_packet(OTHER_PACKET_ID, "NO_ROUTE"),
    )
    await task

    assert (state := hass.states.get(CONFIG_OK_TO_MQTT))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_turn_off_sends_the_whole_section_back(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that clearing a flag is the same round trip as setting one."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(IGNORE_MQTT))
    assert state.state == STATE_ON

    task = await start_call(hass, SERVICE_TURN_OFF, IGNORE_MQTT)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.writeConfig.assert_called_once_with(SECTION_LORA)
    assert admin_writes[0].set_config.lora == config_pb2.Config.LoRaConfig(
        region=config_pb2.Config.LoRaConfig.RegionCode.EU_868,
        modem_preset=config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST,
        hop_limit=3,
        tx_enabled=True,
        tx_power=27,
        channel_num=20,
    )
    assert (state := hass.states.get(IGNORE_MQTT))
    assert state.state == STATE_OFF


async def test_an_unchanged_value_is_never_written(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that writing the value the node already has costs nothing.

    Every ``set_config`` writes flash whether or not anything changed
    (gap 6, case B3b), so a no-op has to stop before the radio.
    """
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(TX_ENABLED))
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TX_ENABLED}, blocking=True
    )

    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []
    assert (state := hass.states.get(TX_ENABLED))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_refused_write_raises_a_translated_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that a routing error from the node becomes a translated error."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_call(hass, SERVICE_TURN_ON, CONFIG_OK_TO_MQTT)
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        routing_packet(ADMIN_PACKET_ID, "BAD_REQUEST"),
    )

    with pytest.raises(ServiceValidationError) as err:
        await task

    assert err.value.translation_key == "rejected_bad_request"
    assert err.value.translation_placeholders == {
        "node": "HA Gateway",
        "reason": "BAD_REQUEST",
        "message": "",
    }
    assert len(admin_writes) == 1
    # The node refused the value, so it must not be shown as if it took.
    assert (state := hass.states.get(CONFIG_OK_TO_MQTT))
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("section", "field"),
    [
        (SECTION_LORA, "region"),
        (SECTION_LORA, "modem_preset"),
        (SECTION_LORA, "tx_power"),
        (SECTION_LORA, "use_preset"),
        (SECTION_LORA, "sx126x_rx_boosted_gain"),
        (SECTION_DEVICE, "role"),
        (SECTION_DEVICE, "rebroadcast_mode"),
        (SECTION_DEVICE, "button_gpio"),
        # A section this integration does not expose at all: ``position``
        # reboots whatever is written to it.
        ("position", "position_broadcast_secs"),
    ],
)
async def test_a_setting_that_reboots_the_node_is_refused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
    section: str,
    field: str,
) -> None:
    """Test that the shared snapshot refuses to write a rebooting setting.

    Nothing exposes these today, and this is the guard that keeps it that way:
    the allow-list is checked before anything reaches the radio, so adding an
    entity for a rebooting field fails here rather than restarting a node.
    """
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    config_snapshot = await async_get_config_snapshot(mock_config_entry)

    with pytest.raises(ServiceValidationError) as err:
        await config_snapshot.async_write(section, field, 1)

    assert err.value.translation_key == "setting_reboots_node"
    assert err.value.translation_placeholders == {"setting": f"{section}.{field}"}
    mock_meshtastic_client.localNode.writeConfig.assert_not_called()
    assert admin_writes == []


async def test_a_node_that_never_reported_its_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test a gateway whose configuration the library never downloaded.

    The switches still exist - they belong to the gateway device, not to the
    configuration - but they have no value to show and refuse to write one.
    """
    mock_meshtastic_client.localNode = SimpleNamespace(localConfig=None)
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert (state := hass.states.get(TX_ENABLED))
    assert state.state == STATE_UNKNOWN

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: TX_ENABLED},
            blocking=True,
        )

    assert err.value.translation_key == "no_config"


def test_every_exposed_switch_is_applied_live() -> None:
    """Test that no switch writes a field the firmware reboots for.

    The lists come from ``AdminModule::handleSetConfig``: a section keeps
    ``requiresReboot`` true unless every field in its own list is unchanged.
    """
    for description in GATEWAY_SWITCHES:
        assert description.field in LIVE_FIELDS[description.section], (
            f"{description.key} writes {description.section}.{description.field}, "
            "which is not on the firmware's live list"
        )
        assert description.field not in REBOOTING_FIELDS[description.section]


def test_node_flag_switches_are_node_database_writes() -> None:
    """Test that the per-node flags only use admin messages that never reboot.

    ``set_favorite_node``/``remove_favorite_node`` (39/40) and
    ``set_ignored_node``/``remove_ignored_node`` (47/48) all end in
    ``saveChanges(SEGMENT_NODEDATABASE, false)``.
    """
    assert {
        method
        for description in NODE_SWITCHES
        for method in (description.set_method, description.clear_method)
    } == {"setFavorite", "removeFavorite", "setIgnored", "removeIgnored"}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_node_flag_switch_writes_the_node_database(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that favouriting a node addresses that node by number."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(REMOTE_IGNORED))
    assert state.state == STATE_OFF

    task = await start_call(hass, SERVICE_TURN_ON, REMOTE_IGNORED)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    # Never a node name: the library looks names up in its own table and calls
    # sys.exit() on a miss.
    mock_meshtastic_client.localNode.setIgnored.assert_called_once_with(REMOTE_NUM)
    mock_meshtastic_client.localNode.removeIgnored.assert_not_called()
    assert (state := hass.states.get(REMOTE_IGNORED))
    assert state.state == STATE_ON
    # Node-database writes go nowhere near set_config.
    assert admin_writes == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_node_flag_switch_clears_the_flag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that turning a node flag off uses the clearing admin message."""
    await setup_switch_platform(
        hass,
        mock_config_entry,
        mock_pubsub,
        mock_meshtastic_client,
        {**node_fixtures, REMOTE_ID: {**node_fixtures[REMOTE_ID], "isFavorite": True}},
    )
    assert (state := hass.states.get(REMOTE_FAVORITE))
    assert state.state == STATE_ON

    task = await start_call(hass, SERVICE_TURN_OFF, REMOTE_FAVORITE)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task

    mock_meshtastic_client.localNode.removeFavorite.assert_called_once_with(REMOTE_NUM)
    mock_meshtastic_client.localNode.setFavorite.assert_not_called()
    assert (state := hass.states.get(REMOTE_FAVORITE))
    assert state.state == STATE_OFF
    assert admin_writes == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_node_flag_switch_defers_to_the_gateway(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that the acknowledged value gives way to the node database.

    The gateway only republishes a flag when it pushes the record again, so
    the acknowledged write is shown in the meantime and dropped as soon as the
    gateway agrees.
    """
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(REMOTE_FAVORITE))
    assert state.state == STATE_OFF

    task = await start_call(hass, SERVICE_TURN_ON, REMOTE_FAVORITE)
    await inject_packet(
        hass, mock_pubsub, mock_meshtastic_client, routing_packet(ADMIN_PACKET_ID)
    )
    await task
    mock_meshtastic_client.localNode.setFavorite.assert_called_once_with(REMOTE_NUM)
    assert (state := hass.states.get(REMOTE_FAVORITE))
    assert state.state == STATE_ON

    await inject_node_info(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        {**node_fixtures[REMOTE_ID], "isFavorite": True},
    )

    assert (state := hass.states.get(REMOTE_FAVORITE))
    assert state.state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_node_flag_switch_failure_keeps_the_old_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    admin_writes: list[admin_pb2.AdminMessage],
) -> None:
    """Test that a node-database write the gateway refuses raises."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    task = await start_call(hass, SERVICE_TURN_ON, REMOTE_FAVORITE)
    await inject_packet(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        routing_packet(ADMIN_PACKET_ID, "NOT_AUTHORIZED"),
    )

    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "admin_not_authorized"
    assert (state := hass.states.get(REMOTE_FAVORITE))
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches_go_unavailable_with_the_link(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that nothing can be written while the node is unreachable."""
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(TX_ENABLED))
    assert state.state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert (state := hass.states.get(TX_ENABLED))
    assert state.state == STATE_UNAVAILABLE
    assert (state := hass.states.get(REMOTE_FAVORITE))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_link_lost_during_setup_still_creates_every_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a node that drops the link while the platforms are being set up.

    Four platforms share one configuration snapshot and the first of them to
    set up is the one that reads it.  A read that fails there must not fail
    that platform - and must not leave the other three registering entities
    against a snapshot that will never be filled either.  Every configuration
    entity is created, with no value, and the next reconnect fills them in.
    """
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.meshtastic")
    mock_meshtastic_client.localNode = LocalNodeThatLosesTheLink(
        mock_meshtastic_client.localNode
    )

    with patch("homeassistant.components.meshtastic.PLATFORMS", CONFIG_PLATFORMS):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    for entity_id in (TX_ENABLED, IGNORE_MQTT, HOP_LIMIT, BUZZER_MODE, TZDEF):
        assert (state := hass.states.get(entity_id)), entity_id
        assert state.state == STATE_UNKNOWN, entity_id
    assert "Could not read the node configuration" in caplog.text
    assert not errors(caplog)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_a_re_read_that_loses_the_link_keeps_the_last_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a re-read that runs into a link that went away again.

    The snapshot is refetched on every reconnect, from a detached task that
    has nowhere to report a failure to.  A link that flaps once more while
    that read is in flight has to leave the values that are on screen alone
    and say so in the debug log, not raise out of the task.
    """
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    assert (state := hass.states.get(TX_ENABLED))
    assert state.state == STATE_ON

    client = mock_config_entry.runtime_data.client
    caplog.clear()
    caplog.set_level(logging.DEBUG, logger="homeassistant.components.meshtastic")
    with patch.object(
        client,
        "async_request",
        side_effect=MeshtasticConnectionError(
            translation_domain=DOMAIN, translation_key="not_connected"
        ),
    ) as request:
        await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)
        await reconnect(hass)

    assert request.await_count == 1
    assert (state := hass.states.get(TX_ENABLED))
    assert state.state == STATE_ON
    assert "Could not read the node configuration" in caplog.text
    assert not errors(caplog)


async def test_the_configuration_snapshot_belongs_to_the_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the snapshot the platforms share is the entry's runtime data.

    It holds the coordinator, the client and a lock, so its lifetime has to be
    the entry's: ``runtime_data`` is dropped when the entry unloads, which a
    module-level table keyed by entry id would not be.
    """
    await setup_switch_platform(
        hass, mock_config_entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    config_snapshot = mock_config_entry.runtime_data.config_snapshot
    assert config_snapshot is not None
    # Every platform gets the same one.
    assert await async_get_config_snapshot(mock_config_entry) is config_snapshot

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(AttributeError):
        _ = mock_config_entry.runtime_data
