"""Tests for the Meshtastic setup, unload and migration."""

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import timedelta
import reprlib
import threading
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.meshtastic import (
    async_migrate_entry,
    async_remove_config_entry_device,
)
from homeassistant.components.meshtastic.client import MeshtasticClient
from homeassistant.components.meshtastic.const import (
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_TRIPS,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    LEGACY_CONF_TCP_HOST,
    LEGACY_CONF_TCP_PORT,
    RECONNECT_MAX_DELAY,
    STORAGE_KEY_FORMAT,
    STORAGE_SAVE_DELAY,
    gateway_device_id,
    node_device_id,
)
from homeassistant.components.meshtastic.coordinator import (
    MeshtasticCoordinator,
    MeshtasticRuntimeData,
)
from homeassistant.components.meshtastic.models import ConnectionState
from homeassistant.components.meshtastic.repairs import (
    ISSUE_CIRCUIT_BREAKER_OPEN,
    ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import get_scheduled_timer_handles

from . import (
    GATEWAY_ID,
    GATEWAY_NUM,
    REMOTE_ID,
    REMOTE_NUM,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed

#: A node number the sample mesh never uses, for the "forgotten node" device.
FORGOTTEN_NUM = 16909060
#: Any state sensor of the gateway; used to see availability flip over.
GATEWAY_CONNECTION_STATE = "sensor.ha_gateway_connection_state"
GATEWAY_LAST_PACKET = "sensor.ha_gateway_last_packet_received"
#: Thread names of Home Assistant's own executor pools, which grow on demand
#: and are not the integration's to clean up.
POOL_THREAD_PREFIXES = ("SyncWorker_", "asyncio_", "DbWorker_", "Recorder")


async def _settle(hass: HomeAssistant) -> None:
    """Let the client's background tasks run.

    The reconnect supervisor and the heartbeat are background tasks, which
    ``async_block_till_done`` deliberately does not wait for, so they need a
    few plain event-loop turns first.
    """
    for _ in range(5):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Fire every timer that is due within ``seconds`` and let it play out."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await _settle(hass)


async def _reconnect(hass: HomeAssistant) -> None:
    """Wait out the reconnect backoff, whatever step it has reached."""
    await _advance(hass, RECONNECT_MAX_DELAY + 1)


@contextmanager
def _full_reprs() -> Generator[None]:
    """Stop ``reprlib`` truncating the job inside a timer handle's repr."""
    limits = reprlib.aRepr.maxstring, reprlib.aRepr.maxother
    reprlib.aRepr.maxstring = reprlib.aRepr.maxother = 300
    try:
        yield
    finally:
        reprlib.aRepr.maxstring, reprlib.aRepr.maxother = limits


def _armed_timers(hass: HomeAssistant, needle: str = "Meshtastic") -> list[str]:
    """Return every event-loop timer the integration still has armed."""
    with _full_reprs():
        return [
            repr(handle)
            for handle in get_scheduled_timer_handles(hass.loop)
            if not handle.cancelled() and needle in repr(handle)
        ]


def _registry_save_timer(hass: HomeAssistant) -> asyncio.TimerHandle:
    """Return the node registry's one armed save timer."""
    with _full_reprs():
        handles = [
            handle
            for handle in get_scheduled_timer_handles(hass.loop)
            if not handle.cancelled() and "MeshtasticNodeRegistry" in repr(handle)
        ]
    assert len(handles) == 1
    return handles[0]


def _running_tasks() -> list[str]:
    """Return the names of the integration's still running asyncio tasks."""
    return [
        task.get_name()
        for task in asyncio.all_tasks()
        if task.get_name().startswith(DOMAIN) and not task.done()
    ]


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the happy path of setting the entry up and unloading it again."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    runtime = mock_config_entry.runtime_data
    assert runtime.client.connected
    assert runtime.coordinator.last_update_success
    assert runtime.coordinator.gateway.node_id == GATEWAY_ID

    # The gateway device is registered before the platforms are forwarded, so
    # node entities can always resolve it as their via_device parent.
    gateway_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_device_id(GATEWAY_NUM)), mock_config_entry.entry_id
    )
    assert gateway_device is not None
    assert gateway_device.manufacturer == "Meshtastic"
    assert gateway_device.model == "TBEAM"
    assert gateway_device.sw_version == "2.7.26.54e0d8d"
    assert gateway_device.serial_number == GATEWAY_ID

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert mock_meshtastic_client.close.call_count == 1
    assert not runtime.client.connected


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_unload_leaves_nothing_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
) -> None:
    """Test that unloading leaves no thread, task or timer behind.

    Hearing a node arms the node registry's save timer, so this covers the
    debounced write as well as the client's supervisor and heartbeat tasks.
    """
    threads_before = {thread.name for thread in threading.enumerate()}

    await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )

    # Everything the integration owns really is armed at this point, so the
    # assertions after the unload are not vacuous.
    assert _armed_timers(hass, "MeshtasticNodeRegistry")
    assert _running_tasks()
    assert mock_pubsub.subscribed_topics

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert _armed_timers(hass) == []
    assert _running_tasks() == []
    assert mock_pubsub.subscribed_topics == set()
    assert {
        thread.name
        for thread in threading.enumerate()
        if thread.name not in threads_before
        and not thread.name.startswith(POOL_THREAD_PREFIXES)
    } == set()


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_node_registry_timer_is_cancelled_on_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    hass_storage: dict[str, Any],
) -> None:
    """Test that shutting Home Assistant down disarms the save timer.

    Config entries are not unloaded at shutdown, so the registry has to clean
    up after itself when it flushes on ``EVENT_HOMEASSISTANT_STOP``; a timer
    that outlives the stop keeps the event loop from closing.
    """
    await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )
    assert _armed_timers(hass, "MeshtasticNodeRegistry")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert _armed_timers(hass, "MeshtasticNodeRegistry") == []
    # The pending snapshot was still written before the timer was dropped.
    key = STORAGE_KEY_FORMAT.format(entry_id=mock_config_entry.entry_id)
    assert REMOTE_ID in hass_storage[key]["data"]["nodes"]

    # A packet that arrives after the shutdown must not arm it again.
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[GATEWAY_ID])
    )
    assert _armed_timers(hass, "MeshtasticNodeRegistry") == []


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_setup_fails_when_the_node_cannot_be_reached(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
) -> None:
    """Test that a failed first connect is retried rather than fatal."""
    mock_meshtastic_client.interface_class.side_effect = OSError("no route to host")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "host": "192.0.2.10"
    }
    # Nothing was left running by the failed attempt.
    assert _running_tasks() == []

    mock_meshtastic_client.interface_class.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_reconnect_recovers_the_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
) -> None:
    """Test that losing the link marks the data stale and reconnecting clears it."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success
    assert hass.states.get(GATEWAY_LAST_PACKET).state != STATE_UNAVAILABLE

    await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)

    assert not coordinator.last_update_success
    assert coordinator.client.connection_state is ConnectionState.RECONNECTING
    assert hass.states.get(GATEWAY_LAST_PACKET).state == STATE_UNAVAILABLE
    # The link diagnostic keeps reporting exactly while the link is down.
    assert hass.states.get(GATEWAY_CONNECTION_STATE).state == "reconnecting"

    # The supervisor backs off before retrying, so the clock has to move on.
    await _settle(hass)
    await _reconnect(hass)

    assert coordinator.client.connection_state is ConnectionState.CONNECTED
    assert coordinator.last_update_success
    assert hass.states.get(GATEWAY_LAST_PACKET).state != STATE_UNAVAILABLE
    assert mock_meshtastic_client.interface_class.call_count == 2


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_circuit_breaker_opens_and_raises_a_repair(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that repeated kicks pause reconnection and tell the user why.

    A Meshtastic node serves one API client at a time and force-closes the one
    it drops, so a phone app left running looks exactly like this.  The issue
    is raised by the coordinator listener ``async_setup_entry`` installs, so
    nothing has to be reconciled by hand here.
    """
    await setup_integration(hass, mock_config_entry)

    client = mock_config_entry.runtime_data.client
    for _ in range(CIRCUIT_BREAKER_TRIPS):
        assert client.connected
        await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)
        await _settle(hass)
        await _reconnect(hass)

    assert client.stats()["short_connections"] == CIRCUIT_BREAKER_TRIPS
    assert client.stats()["circuit_breaker_open"] is True
    assert client.connection_state is ConnectionState.CIRCUIT_OPEN

    issue = issue_registry.async_get_issue(
        DOMAIN, f"{ISSUE_CIRCUIT_BREAKER_OPEN}_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_placeholders == {
        "name": "HA Gateway",
        "host": "192.0.2.10",
        "count": str(CIRCUIT_BREAKER_TRIPS),
        "seconds": str(int(CIRCUIT_BREAKER_COOLDOWN)),
    }

    # Once the cooldown elapses the client reconnects and the issue goes away.
    await _advance(hass, CIRCUIT_BREAKER_COOLDOWN + 10)

    assert client.connection_state is ConnectionState.CONNECTED
    assert (
        issue_registry.async_get_issue(
            DOMAIN, f"{ISSUE_CIRCUIT_BREAKER_OPEN}_{mock_config_entry.entry_id}"
        )
        is None
    )


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_unloading_withdraws_the_live_issues(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a repair about a link goes away with the link."""
    await setup_integration(hass, mock_config_entry)

    for _ in range(CIRCUIT_BREAKER_TRIPS):
        await inject_connection_lost(hass, mock_pubsub, mock_meshtastic_client)
        await _settle(hass)
        await _reconnect(hass)

    issue_id = f"{ISSUE_CIRCUIT_BREAKER_OPEN}_{mock_config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_nodes_survive_a_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    hass_storage: dict[str, Any],
) -> None:
    """Test that the node table is persisted and read back on the next start."""
    await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )
    key = STORAGE_KEY_FORMAT.format(entry_id=mock_config_entry.entry_id)
    assert key not in hass_storage

    # The save is debounced, but armed once and never pushed out, so it fires
    # however busy the mesh is.
    await _advance(hass, STORAGE_SAVE_DELAY + 5)

    stored = hass_storage[key]
    assert stored["version"] == 1
    assert stored["minor_version"] == 1
    assert set(stored["data"]["nodes"]) == {GATEWAY_ID, REMOTE_ID}
    assert stored["data"]["nodes"][REMOTE_ID]["long_name"] == "Remote One"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Nothing has been injected since the restart: this is the stored table.
    nodes = mock_config_entry.runtime_data.coordinator.data.nodes
    assert set(nodes) == {GATEWAY_ID, REMOTE_ID}
    assert nodes[REMOTE_ID].long_name == "Remote One"
    assert nodes[REMOTE_ID].position is not None
    assert not nodes[REMOTE_ID].presumptive


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_a_busy_mesh_cannot_starve_the_node_table_save(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    hass_storage: dict[str, Any],
) -> None:
    """Test that a steady stream of updates cannot postpone the save forever.

    ``Store.async_delay_save`` is a trailing-edge debounce: every further
    update pushes the write out again, so a mesh that is never quiet for
    ``STORAGE_SAVE_DELAY`` seconds would never be persisted at all.  The
    registry arms its own timer once and leaves it alone, which is only
    visible as the deadline not moving while the updates keep coming.
    """
    await setup_integration(hass, mock_config_entry)
    key = STORAGE_KEY_FORMAT.format(entry_id=mock_config_entry.entry_id)
    node = dict(node_fixtures[REMOTE_ID])

    await inject_node_info(hass, mock_pubsub, mock_meshtastic_client, node)
    deadline = _registry_save_timer(hass).when()

    # A busy mesh: every one of these is a change worth persisting.
    for last_heard in range(1757300701, 1757300706):
        await inject_node_info(
            hass, mock_pubsub, mock_meshtastic_client, node | {"lastHeard": last_heard}
        )
        assert key not in hass_storage
        assert _registry_save_timer(hass).when() == deadline

    await _advance(hass, STORAGE_SAVE_DELAY + 1)

    stored = hass_storage[key]["data"]["nodes"]
    assert stored[REMOTE_ID]["last_heard_device"] == 1757300705


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_removing_the_entry_deletes_the_stored_nodes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    hass_storage: dict[str, Any],
) -> None:
    """Test that removing the entry takes its persisted node table with it."""
    await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )
    await _advance(hass, STORAGE_SAVE_DELAY + 5)
    key = STORAGE_KEY_FORMAT.format(entry_id=mock_config_entry.entry_id)
    assert key in hass_storage

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert key not in hass_storage


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_remove_stale_node_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pubsub: FakePubSub,
    mock_meshtastic_client: MagicMock,
    node_fixtures: dict[str, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test which devices the user is allowed to delete by hand.

    A node the mesh has forgotten can go; a node it still knows and the
    gateway itself cannot, because they would come straight back.
    """
    await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, dict(node_fixtures[REMOTE_ID])
    )

    gateway_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_device_id(GATEWAY_NUM)), mock_config_entry.entry_id
    )
    assert gateway_device is not None
    known_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, node_device_id(GATEWAY_NUM, REMOTE_NUM))},
    )
    forgotten_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, node_device_id(GATEWAY_NUM, FORGOTTEN_NUM))},
    )

    assert (
        await async_remove_config_entry_device(
            hass, mock_config_entry, forgotten_device
        )
        is True
    )
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, known_device)
        is False
    )
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, gateway_device)
        is False
    )


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_migrate_entry_from_the_custom_integration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that an entry left by the HACS custom integration is carried over.

    That integration stores the address under ``tcp_host`` / ``tcp_port``.
    Without the migration the entry survives uninstalling the custom component
    and then fails with a ``KeyError`` on every start.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meshtastic",
        unique_id=GATEWAY_ID,
        data={LEGACY_CONF_TCP_HOST: "192.0.2.10", LEGACY_CONF_TCP_PORT: 4404},
        version=1,
        minor_version=0,
    )

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == CONFIG_ENTRY_VERSION
    assert entry.minor_version == CONFIG_ENTRY_MINOR_VERSION
    assert entry.data == {CONF_HOST: "192.0.2.10", CONF_PORT: 4404}

    # The custom integration is still installed and would keep fighting for the
    # node's single client slot, which only the user can fix.
    issue = issue_registry.async_get_issue(
        DOMAIN, f"{ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION}_{entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_persistent is True


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_migrate_entry_without_a_tcp_host(hass: HomeAssistant) -> None:
    """Test that a serial entry from the custom integration is refused."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meshtastic",
        unique_id=GATEWAY_ID,
        data={"serial_port": "/dev/ttyUSB0"},
        version=1,
        minor_version=0,
    )

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert entry.data == {"serial_port": "/dev/ttyUSB0"}


@pytest.mark.parametrize(
    ("version", "migrated"),
    [
        pytest.param(1, True, id="nothing_to_migrate"),
        pytest.param(2, False, id="written_by_a_newer_home_assistant"),
    ],
)
async def test_migrate_entry_leaves_a_usable_entry_alone(
    hass: HomeAssistant, version: int, migrated: bool
) -> None:
    """Test the entries the migration has nothing to do to.

    An entry that already has a TCP host is fine as it is; one written by a
    newer Home Assistant is refused rather than downgraded.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GATEWAY_ID,
        data={CONF_HOST: "192.0.2.10", CONF_PORT: 4403},
        version=version,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is migrated
    assert entry.version == version
    assert entry.data == {CONF_HOST: "192.0.2.10", CONF_PORT: 4403}
    # The minor version is recorded either way, so the entry is not migrated
    # again on every start.
    if migrated:
        assert entry.minor_version == CONFIG_ENTRY_MINOR_VERSION


@pytest.mark.usefixtures("mock_meshtastic_client")
async def test_migrate_entry_left_behind_at_the_first_minor_version(
    hass: HomeAssistant,
) -> None:
    """Test that a 1.1 entry from the custom integration is still converted.

    Home Assistant only calls ``async_migrate_entry`` when the stored version
    differs from the flow's, which is why ``CONFIG_ENTRY_MINOR_VERSION`` is 2:
    the custom integration left its entries at 1.1.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meshtastic",
        unique_id=GATEWAY_ID,
        data={LEGACY_CONF_TCP_HOST: "192.0.2.10", LEGACY_CONF_TCP_PORT: 4404},
        version=1,
        minor_version=1,
    )

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == CONFIG_ENTRY_MINOR_VERSION
    assert entry.data == {CONF_HOST: "192.0.2.10", CONF_PORT: 4404}


async def test_remove_device_before_the_first_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that no device may be deleted until the gateway has been heard.

    Without a gateway identity there is no way to tell a node the mesh forgot
    from one it never got round to reporting.
    """
    mock_config_entry.add_to_hass(hass)
    client = MeshtasticClient(hass, "192.0.2.10", 4403)
    coordinator = MeshtasticCoordinator(hass, mock_config_entry, client)
    mock_config_entry.runtime_data = MeshtasticRuntimeData(
        client=client, coordinator=coordinator
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, node_device_id(GATEWAY_NUM, FORGOTTEN_NUM))},
    )

    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, device) is False
    )

    await coordinator.async_shutdown()
