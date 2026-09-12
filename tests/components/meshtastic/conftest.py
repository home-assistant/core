"""Fixtures for the Meshtastic integration tests."""

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

# Importing the library here, at collection time, starts its module-global
# "publishing" daemon thread before the lingering-thread check snapshots the
# running threads.  Do not move this into a fixture.
from meshtastic.protobuf import channel_pb2, config_pb2, localonly_pb2, mesh_pb2
import pytest

from homeassistant.components.meshtastic.const import (
    CONF_DOWNLOAD_NODE_DB,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import GATEWAY_ID, GATEWAY_NUM, FakePubSub

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry, for config-flow tests."""
    with patch(
        "homeassistant.components.meshtastic.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Meshtastic config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HA Gateway",
        unique_id=GATEWAY_ID,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_DOWNLOAD_NODE_DB: False,
        },
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )


@pytest.fixture
def gateway_my_info() -> mesh_pb2.MyNodeInfo:
    """Return the gateway's MyNodeInfo protobuf."""
    return mesh_pb2.MyNodeInfo(my_node_num=GATEWAY_NUM, reboot_count=7, nodedb_count=3)


@pytest.fixture
def gateway_metadata() -> mesh_pb2.DeviceMetadata:
    """Return the gateway's DeviceMetadata protobuf."""
    return mesh_pb2.DeviceMetadata(
        firmware_version="2.7.26.54e0d8d",
        device_state_version=24,
        hw_model=mesh_pb2.HardwareModel.TBEAM,
        role=config_pb2.Config.DeviceConfig.Role.CLIENT,
        hasWifi=True,
        hasBluetooth=True,
    )


@pytest.fixture
def gateway_local_node() -> SimpleNamespace:
    """Return a stand-in for ``interface.localNode``."""
    local_config = localonly_pb2.LocalConfig()
    local_config.lora.region = config_pb2.Config.LoRaConfig.RegionCode.EU_868
    local_config.lora.modem_preset = config_pb2.Config.LoRaConfig.ModemPreset.LONG_FAST
    local_config.lora.hop_limit = 3
    local_config.device.role = config_pb2.Config.DeviceConfig.Role.CLIENT

    primary = channel_pb2.Channel(index=0, role=channel_pb2.Channel.Role.PRIMARY)
    primary.settings.psk = b"\x01"
    admin = channel_pb2.Channel(index=1, role=channel_pb2.Channel.Role.SECONDARY)
    admin.settings.name = "admin"
    admin.settings.psk = b"0123456789abcdef"
    disabled = channel_pb2.Channel(index=2, role=channel_pb2.Channel.Role.DISABLED)

    return SimpleNamespace(
        nodeNum=GATEWAY_NUM,
        localConfig=local_config,
        moduleConfig=localonly_pb2.LocalModuleConfig(),
        channels=[primary, admin, disabled],
    )


@pytest.fixture
async def node_fixtures(hass: HomeAssistant) -> dict[str, Any]:
    """Return the sample node database, keyed by node id."""
    return await async_load_json_object_fixture(hass, "nodes.json", DOMAIN)


@pytest.fixture
async def packet_fixtures(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return the sample packets, keyed by the fixture name without suffix."""
    names = (
        "packet_text",
        "packet_text_direct",
        "packet_position",
        "packet_telemetry_device",
        "packet_telemetry_environment",
        "packet_nodeinfo",
        "packet_routing_ack",
        "packet_routing_nak",
        "packet_traceroute",
        "packet_encrypted",
    )
    return {
        name: await async_load_json_object_fixture(hass, f"{name}.json", DOMAIN)
        for name in names
    }


@pytest.fixture
def mock_pubsub() -> Generator[FakePubSub]:
    """Replace the library's pubsub publisher with a recording stand-in.

    Tests use the returned object to invoke the callbacks the client
    registered, which is how packets are injected.
    """
    fake = FakePubSub()
    with patch("homeassistant.components.meshtastic.client.pub", fake):
        yield fake


@pytest.fixture
def mock_meshtastic_client(
    gateway_my_info: mesh_pb2.MyNodeInfo,
    gateway_metadata: mesh_pb2.DeviceMetadata,
    gateway_local_node: SimpleNamespace,
    node_fixtures: dict[str, Any],
    mock_pubsub: FakePubSub,
) -> Generator[MagicMock]:
    """Mock the interface class and yield the connected instance.

    ``autospec=True`` means the mock only answers to the library's real public
    API, so a typo or a call into a private method fails the test.  Instance
    attributes the constructor would have created are set explicitly.
    """
    with patch(
        "homeassistant.components.meshtastic.client.MeshtasticInterface", autospec=True
    ) as mock_interface:
        interface = mock_interface.return_value
        interface.myInfo = gateway_my_info
        interface.metadata = gateway_metadata
        interface.localNode = gateway_local_node
        interface.queueStatus = mesh_pb2.QueueStatus(free=16, maxlen=16)

        def _connect(*_args: Any, noNodes: bool = False, **_kwargs: Any) -> MagicMock:
            """Fill the node table the way the handshake does.

            ``_startConfig()`` empties ``nodes``/``nodesByNum`` and the node
            streams them back before the constructor returns.  Under the
            nodeless nonce 69420 the firmware skips everyone else's
            ``NodeInfo`` but still sends its own, which is exactly the
            difference the ``download_node_db`` option makes.
            """
            table = (
                {GATEWAY_ID: node_fixtures[GATEWAY_ID]}
                if noNodes
                else dict(node_fixtures)
            )
            interface.nodes = table
            interface.nodesByNum = {node["num"]: node for node in table.values()}
            return interface

        mock_interface.side_effect = _connect
        _connect(noNodes=True)
        interface.getMyNodeInfo.return_value = node_fixtures[GATEWAY_ID]
        interface.sendText.side_effect = lambda *args, **kwargs: mesh_pb2.MeshPacket(
            id=111222333
        )
        interface.sendData.side_effect = lambda *args, **kwargs: mesh_pb2.MeshPacket(
            id=111222334
        )
        interface.sendHeartbeat.return_value = None
        interface.close.return_value = None
        # Keep a handle on the class mock so tests can assert constructor args.
        interface.interface_class = mock_interface
        yield interface
