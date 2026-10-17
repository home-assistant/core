"""Tests for the Meshtastic diagnostics.

The download is one of the two support artefacts a user is asked for, and
the log is the other, so the tests for what may leave the mesh live
together here.
"""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.logger.helpers import get_integration_loggers
from homeassistant.components.meshtastic.const import (
    CONF_DOWNLOAD_NODE_DB,
    CONF_INCLUDE_LOCATION,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_PORT,
    DOMAIN,
    HEARTBEAT_INTERVAL,
    gateway_device_id,
    node_device_id,
)
from homeassistant.components.meshtastic.diagnostics import (
    TO_REDACT_LOCATION,
    TO_REDACT_SECRETS,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    REMOTE_NUM,
    SENSOR_NODE_ID,
    FakePubSub,
    inject_node_info,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator

# Just after the newest node fixture, so the node table is fully populated and
# every timestamp in the dump is deterministic.
FROZEN_TIME = "2025-09-08 02:57:10+00:00"

#: The address of the node under test.  Documentation range, never routable.
HOST = "192.0.2.10"

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)

#: A raw record carrying every secret name the module knows how to redact, one
#: value per name so a missing name shows up as its own plaintext value.  A
#: Meshtastic config entry only holds the host, the port and the node-DB flag
#: today, but the redaction list exists for what the dump may grow to carry -
#: the node's channel PSKs, its private and admin keys, the administration
#: session passkey and the Wi-Fi and MQTT credentials - and for anything an
#: entry inherited from the custom integration left behind.  Nesting it inside
#: the entry proves the redaction reaches into nested records as well.
SECRET_RECORD: dict[str, str] = {key: f"plaintext-{key}" for key in TO_REDACT_SECRETS}

#: A raw position record in every spelling the firmware and the library use.
LOCATION_RECORD: dict[str, float] = dict.fromkeys(TO_REDACT_LOCATION, 52.1234567)

#: The coordinates of the two nodes that report a position in ``nodes.json``.
GATEWAY_LATITUDE = 52.1234567
GATEWAY_LONGITUDE = 13.1234567
REMOTE_LATITUDE = 52.1111111
REMOTE_LONGITUDE = 13.1111111


def _entry(options: dict[str, Any] | None = None) -> MockConfigEntry:
    """Return a config entry whose data carries every redactable name."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="HA Gateway",
        unique_id=GATEWAY_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_DOWNLOAD_NODE_DB: False,
            "node_config": SECRET_RECORD,
            "fixed_position": LOCATION_RECORD,
        },
        options=options or {},
        version=CONFIG_ENTRY_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )


async def _setup_with_nodes(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    pubsub: FakePubSub,
    interface: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Set up the entry and make all three sample nodes known."""
    await setup_integration(hass, entry)
    for node_id in (GATEWAY_ID, REMOTE_ID, SENSOR_NODE_ID):
        await inject_node_info(hass, pubsub, interface, node_fixtures[node_id])


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the config entry diagnostics download."""
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


async def test_device_diagnostics_gateway(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics download of the gateway device."""
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_device_id(GATEWAY_NUM)), entry.entry_id
    )
    assert device is not None

    result = await get_diagnostics_for_device(hass, hass_client, entry, device)

    assert result["is_gateway"] is True
    assert result == snapshot


async def test_device_diagnostics_node(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics download of one mesh node sub-device."""
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, node_device_id(GATEWAY_NUM, REMOTE_NUM)), entry.entry_id
    )
    assert device is not None

    result = await get_diagnostics_for_device(hass, hass_client, entry, device)

    assert result["is_gateway"] is False
    # A node sub-device reports the node, not the shared link statistics.
    assert result["gateway"] is None
    assert result["connection"] is None
    assert result == snapshot


async def test_device_diagnostics_unknown_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the diagnostics of a device whose node the mesh has forgotten."""
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, node_device_id(GATEWAY_NUM, 1))},
    )

    result = await get_diagnostics_for_device(hass, hass_client, entry, device)

    assert result["is_gateway"] is False
    assert result["node"] is None


@pytest.mark.parametrize("secret", sorted(TO_REDACT_SECRETS))
async def test_config_entry_diagnostics_redacts_every_secret(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    secret: str,
) -> None:
    """Test that every secret name is redacted, wherever it appears.

    The list covers the channel pre-shared keys, the node's private and admin
    keys, the administration session passkey and the Wi-Fi and MQTT passwords,
    in both the protobuf and the library spelling.
    """
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    data = result["entry"]["data"]

    assert data["node_config"][secret] == REDACTED
    assert SECRET_RECORD[secret] not in str(result)


async def test_config_entry_diagnostics_redacts_host(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the node's address is redacted everywhere it is reported."""
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["entry"]["data"][CONF_HOST] == REDACTED
    assert result["connection"]["host"] == REDACTED
    assert HOST not in str(result)


@pytest.mark.parametrize("key", sorted(TO_REDACT_LOCATION))
async def test_config_entry_diagnostics_redacts_coordinates(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    key: str,
) -> None:
    """Test that every spelling of a coordinate is redacted by default."""
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["entry"]["data"]["fixed_position"][key] == REDACTED


async def test_config_entry_diagnostics_redacts_node_positions(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that the reported position of every node is redacted by default.

    A Meshtastic node is very often a person, so the download must not put the
    mesh on a map unless the user asked for it.
    """
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    for node_id in (GATEWAY_ID, REMOTE_ID):
        position = result["nodes"][node_id]["position"]
        assert position["latitude"] == REDACTED
        assert position["longitude"] == REDACTED
        # Everything that explains the fix is kept; only the fix itself goes.
        assert position["altitude"] is not None

    for coordinate in (
        GATEWAY_LATITUDE,
        GATEWAY_LONGITUDE,
        REMOTE_LATITUDE,
        REMOTE_LONGITUDE,
    ):
        assert str(coordinate) not in str(result)


async def test_device_diagnostics_redacts_node_position(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a single device download redacts the node's position too."""
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, node_device_id(GATEWAY_NUM, REMOTE_NUM)), entry.entry_id
    )
    assert device is not None

    result = await get_diagnostics_for_device(hass, hass_client, entry, device)

    assert result["node"]["position"]["latitude"] == REDACTED
    assert result["node"]["position"]["longitude"] == REDACTED


async def test_diagnostics_include_location_option(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that opting in reports coordinates but still redacts the secrets."""
    entry = _entry({CONF_INCLUDE_LOCATION: True})
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["nodes"][GATEWAY_ID]["position"]["latitude"] == GATEWAY_LATITUDE
    assert result["nodes"][GATEWAY_ID]["position"]["longitude"] == GATEWAY_LONGITUDE
    assert result["nodes"][REMOTE_ID]["position"]["latitude"] == REMOTE_LATITUDE
    assert result["nodes"][REMOTE_ID]["position"]["longitude"] == REMOTE_LONGITUDE
    assert result["entry"]["data"]["fixed_position"]["latitude"] == GATEWAY_LATITUDE

    # Opting in to coordinates never opts in to key material.
    for secret in TO_REDACT_SECRETS:
        assert result["entry"]["data"]["node_config"][secret] == REDACTED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, node_device_id(GATEWAY_NUM, REMOTE_NUM)), entry.entry_id
    )
    assert device is not None
    device_result = await get_diagnostics_for_device(hass, hass_client, entry, device)
    assert device_result["node"]["position"]["latitude"] == REMOTE_LATITUDE


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Fire every timer due within ``seconds`` and let the tasks run.

    The client's heartbeat is a background task, which
    ``async_block_till_done`` deliberately does not wait for.
    """
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    for _ in range(5):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


async def test_diagnostics_redacts_the_host_in_the_text_of_errors(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that a dead link does not spell the node's address out in prose.

    Every connection error the client raises carries the address as a
    translation placeholder, so the rendered message ends up inside
    ``dead_reason`` and inside the coordinator's last exception - values that
    no key-based redaction can reach.
    """
    entry = _entry()
    await _setup_with_nodes(
        hass, entry, mock_pubsub, mock_meshtastic_client, node_fixtures
    )

    # The ordinary way a Meshtastic link dies: the node stops answering.
    mock_meshtastic_client.sendHeartbeat.side_effect = OSError("broken pipe")
    await _advance(hass, HEARTBEAT_INTERVAL + 1)

    # The address really is in the text the dump reports; that is the point.
    assert HOST in entry.runtime_data.client.stats()["dead_reason"]

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert HOST not in str(result)
    assert REDACTED in result["errors"]["dead_reason"]
    assert REDACTED in result["errors"]["last_exception"]
    assert REDACTED in result["connection"]["dead_reason"]

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_device_id(GATEWAY_NUM)), entry.entry_id
    )
    assert device is not None
    device_result = await get_diagnostics_for_device(hass, hass_client, entry, device)

    assert HOST not in str(device_result)
    assert REDACTED in device_result["connection"]["dead_reason"]


#: The library modules that write key material or message plaintext to the log
#: at ``DEBUG``: ``mesh_interface`` dumps every ``FromRadio`` frame raw and
#: parsed and every decoded packet dict, ``stream_interface`` dumps every frame
#: it writes, ``node`` dumps the channel list, and the package root dumps the
#: decoded text and admin payloads.  The config handshake carries the channel
#: pre-shared keys, the node's private and admin keys, the Wi-Fi PSK and the
#: MQTT password, so none of these may be reachable from the manifest.
UNSAFE_LIBRARY_LOGGERS = (
    "meshtastic",
    "meshtastic.mesh_interface",
    "meshtastic.node",
    "meshtastic.stream_interface",
)


async def test_debug_logging_cannot_dump_key_material(hass: HomeAssistant) -> None:
    """Test that enabling debug logging cannot write secrets to the log.

    "Enable debug logging" sets every logger the manifest declares to DEBUG,
    and a child logger inherits the level of any declared ancestor, so
    declaring the library's root logger would put the channel pre-shared keys,
    the node's private key and the plaintext of every message into the file
    the user then attaches to a bug report.
    """
    loggers = await get_integration_loggers(hass, DOMAIN)

    for unsafe in UNSAFE_LIBRARY_LOGGERS:
        assert not any(
            unsafe == logger or unsafe.startswith(f"{logger}.") for logger in loggers
        ), f"debug logging would raise {unsafe} to DEBUG"

    # What is left is still enough to debug a link: the integration's own
    # logger, and the library's socket-level one, which logs no payload.
    assert f"homeassistant.components.{DOMAIN}" in loggers
    assert "meshtastic.tcp_interface" in loggers
