"""Tests for the Meshtastic repair issues."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.meshtastic.const import (
    ATTR_ENTRY_ID,
    ATTR_NODE_ID,
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_TRIPS,
    DOMAIN,
    RECONNECT_MAX_DELAY,
)
from homeassistant.components.meshtastic.models import ConnectionState
from homeassistant.components.meshtastic.repairs import (
    ATTR_NOTICED_AT,
    ISSUE_CIRCUIT_BREAKER_OPEN,
    ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION,
    ISSUE_NODE_UNRESPONSIVE,
    MeshtasticReconnectRepairFlow,
    async_check_issues,
    async_create_fix_flow,
    async_create_migration_issue,
    async_delete_issues,
    async_report_unresponsive_node,
)
from homeassistant.components.repairs import ConfirmRepairFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    REMOTE_ID,
    SENSOR_NODE_ID,
    FakePubSub,
    inject_connection_lost,
    inject_node_info,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

# After every timestamp in the node fixtures, so a node counts as unheard until
# the test says otherwise.
FROZEN_TIME = "2025-09-08 04:00:00+00:00"

pytestmark = pytest.mark.freeze_time(FROZEN_TIME)


async def _settle(hass: HomeAssistant) -> None:
    """Let the client's background tasks make progress.

    The reconnect supervisor and the heartbeat are background tasks, which
    ``async_block_till_done`` deliberately does not wait for.
    """
    for _ in range(5):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    """Fire the client's timers that are due within ``seconds``."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await _settle(hass)


async def _trip_circuit_breaker(
    hass: HomeAssistant, pubsub: FakePubSub, interface: MagicMock
) -> None:
    """Get kicked off the node often enough for the breaker to open.

    Every reconnect is answered immediately by the mocked interface and the
    frozen clock makes each connection zero seconds long, so each cycle counts
    as one more short connection.
    """
    for _ in range(CIRCUIT_BREAKER_TRIPS):
        await inject_connection_lost(hass, pubsub, interface)
        await _settle(hass)
        # Long enough for the longest reconnect backoff, short enough to leave
        # the breaker's own cooldown running.
        await _advance(hass, RECONNECT_MAX_DELAY + 5)


def _breaker_issue_id(entry: MockConfigEntry) -> str:
    """Return the circuit-breaker issue id of an entry."""
    return f"{ISSUE_CIRCUIT_BREAKER_OPEN}_{entry.entry_id}"


def _node_issue_id(entry: MockConfigEntry, node_id: str) -> str:
    """Return the unresponsive-node issue id of one node."""
    return f"{ISSUE_NODE_UNRESPONSIVE}_{entry.entry_id}_{node_id}"


def _migration_issue_id(entry: MockConfigEntry) -> str:
    """Return the migration issue id of an entry."""
    return f"{ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION}_{entry.entry_id}"


async def test_no_issues_on_a_healthy_link(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that a connected gateway raises nothing."""
    await setup_integration(hass, mock_config_entry)

    async_check_issues(hass, mock_config_entry)

    assert not issue_registry.issues


async def test_circuit_breaker_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test the issue raised when another client keeps taking the node."""
    await setup_integration(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client

    await _trip_circuit_breaker(hass, mock_pubsub, mock_meshtastic_client)
    assert client.stats()["circuit_breaker_open"] is True
    assert client.connection_state is ConnectionState.CIRCUIT_OPEN

    # ``__init__`` reconciles the issues on every coordinator update, so the
    # issue is already there; calling the check again must change nothing.
    assert (
        issue_registry.async_get_issue(DOMAIN, _breaker_issue_id(mock_config_entry))
        is not None
    )
    async_check_issues(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(DOMAIN, _breaker_issue_id(mock_config_entry))
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.is_persistent is False
    assert issue.issue_domain == DOMAIN
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == ISSUE_CIRCUIT_BREAKER_OPEN
    assert issue.translation_placeholders == {
        "name": "HA Gateway",
        "host": "192.0.2.10",
        "count": str(CIRCUIT_BREAKER_TRIPS),
        "seconds": str(int(CIRCUIT_BREAKER_COOLDOWN)),
    }
    assert issue.data == {ATTR_ENTRY_ID: mock_config_entry.entry_id}


async def test_circuit_breaker_issue_clears_when_the_link_recovers(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that the issue withdraws itself once reconnecting works again."""
    await setup_integration(hass, mock_config_entry)
    client = mock_config_entry.runtime_data.client

    await _trip_circuit_breaker(hass, mock_pubsub, mock_meshtastic_client)
    async_check_issues(hass, mock_config_entry)
    assert (
        issue_registry.async_get_issue(DOMAIN, _breaker_issue_id(mock_config_entry))
        is not None
    )

    # Let the cooldown elapse; the mocked node answers, so the link is back.
    await _advance(hass, CIRCUIT_BREAKER_COOLDOWN + 10)
    assert client.stats()["circuit_breaker_open"] is False
    assert client.connection_state is ConnectionState.CONNECTED

    async_check_issues(hass, mock_config_entry)

    assert (
        issue_registry.async_get_issue(DOMAIN, _breaker_issue_id(mock_config_entry))
        is None
    )


async def test_circuit_breaker_fix_flow_reloads_the_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that confirming the repair reconnects straight away."""
    assert await async_setup_component(hass, "repairs", {})
    await setup_integration(hass, mock_config_entry)
    first_client = mock_config_entry.runtime_data.client

    await _trip_circuit_breaker(hass, mock_pubsub, mock_meshtastic_client)
    async_check_issues(hass, mock_config_entry)
    issue_id = _breaker_issue_id(mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"]["host"] == "192.0.2.10"

    data = await process_repair_fix_flow(client, data["flow_id"])
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    # The entry was reloaded, so the cooldown is gone and the link is fresh.
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is not first_client
    assert mock_config_entry.runtime_data.client.connected is True
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_circuit_breaker_fix_flow_survives_a_removed_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test confirming the repair of a config entry that is already gone.

    Unloading an entry withdraws its live issues, but the user can be looking
    at the repair while the entry is being removed in another tab.  Confirming
    it then has to acknowledge the issue rather than reload an entry that no
    longer exists, which raises.
    """
    assert await async_setup_component(hass, "repairs", {})
    issue_id = f"{ISSUE_CIRCUIT_BREAKER_OPEN}_gone"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        data={ATTR_ENTRY_ID: "gone"},
        is_fixable=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_CIRCUIT_BREAKER_OPEN,
        translation_placeholders={
            "name": "HA Gateway",
            "host": "192.0.2.10",
            "count": str(CIRCUIT_BREAKER_TRIPS),
            "seconds": str(int(CIRCUIT_BREAKER_COOLDOWN)),
        },
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    data = await process_repair_fix_flow(client, data["flow_id"])

    assert data["type"] == "create_entry"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_unresponsive_node_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
) -> None:
    """Test the issue raised when a node never comes back from a reboot."""
    await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, node_fixtures[REMOTE_ID]
    )

    async_report_unresponsive_node(hass, mock_config_entry, REMOTE_ID)

    issue = issue_registry.async_get_issue(
        DOMAIN, _node_issue_id(mock_config_entry, REMOTE_ID)
    )
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.issue_domain == DOMAIN
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == ISSUE_NODE_UNRESPONSIVE
    assert issue.translation_placeholders == {
        "name": "Remote One",
        "node_id": REMOTE_ID,
        "gateway": "HA Gateway",
    }
    assert issue.data == {
        ATTR_ENTRY_ID: mock_config_entry.entry_id,
        ATTR_NODE_ID: REMOTE_ID,
        ATTR_NOTICED_AT: dt_util.utcnow().isoformat(),
    }


async def test_unresponsive_node_issue_for_an_unknown_node(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that a node the table has forgotten is named by its id."""
    await setup_integration(hass, mock_config_entry)

    async_report_unresponsive_node(hass, mock_config_entry, REMOTE_ID)

    issue = issue_registry.async_get_issue(
        DOMAIN, _node_issue_id(mock_config_entry, REMOTE_ID)
    )
    assert issue is not None
    assert issue.translation_placeholders == {
        "name": REMOTE_ID,
        "node_id": REMOTE_ID,
        "gateway": "HA Gateway",
    }


async def test_unresponsive_node_issue_clears_when_the_node_is_heard(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that hearing from the node again withdraws the issue."""
    await setup_integration(hass, mock_config_entry)
    await inject_node_info(
        hass, mock_pubsub, mock_meshtastic_client, node_fixtures[REMOTE_ID]
    )
    async_report_unresponsive_node(hass, mock_config_entry, REMOTE_ID)
    issue_id = _node_issue_id(mock_config_entry, REMOTE_ID)

    # Still silent: the last time the node was heard predates the report.
    async_check_issues(hass, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    freezer.tick(timedelta(seconds=30))
    await inject_node_info(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        {
            **node_fixtures[REMOTE_ID],
            "lastHeard": int(dt_util.utcnow().timestamp()),
        },
    )

    async_check_issues(hass, mock_config_entry)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_unresponsive_node_issue_left_alone_for_other_nodes(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
    node_fixtures: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that hearing one node does not clear the issue of another."""
    await setup_integration(hass, mock_config_entry)
    for node_id in (REMOTE_ID, SENSOR_NODE_ID):
        await inject_node_info(
            hass, mock_pubsub, mock_meshtastic_client, node_fixtures[node_id]
        )
    async_report_unresponsive_node(hass, mock_config_entry, REMOTE_ID)
    async_report_unresponsive_node(hass, mock_config_entry, SENSOR_NODE_ID)

    freezer.tick(timedelta(seconds=30))
    await inject_node_info(
        hass,
        mock_pubsub,
        mock_meshtastic_client,
        {
            **node_fixtures[SENSOR_NODE_ID],
            "lastHeard": int(dt_util.utcnow().timestamp()),
        },
    )

    async_check_issues(hass, mock_config_entry)

    assert (
        issue_registry.async_get_issue(
            DOMAIN, _node_issue_id(mock_config_entry, REMOTE_ID)
        )
        is not None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, _node_issue_id(mock_config_entry, SENSOR_NODE_ID)
        )
        is None
    )


async def test_migration_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the issue raised for an entry inherited from HACS."""
    assert await async_setup_component(hass, "repairs", {})
    mock_config_entry.add_to_hass(hass)

    async_create_migration_issue(hass, mock_config_entry)

    issue_id = _migration_issue_id(mock_config_entry)
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is True
    # It survives a restart, because the migration itself only happens once.
    assert issue.is_persistent is True
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION
    assert issue.translation_placeholders == {
        "name": "HA Gateway",
        "host": "192.0.2.10",
    }

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"
    data = await process_repair_fix_flow(client, data["flow_id"])

    assert data["type"] == "create_entry"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_async_delete_issues(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    mock_pubsub: FakePubSub,
) -> None:
    """Test that unloading withdraws the live issues but not the migration."""
    await setup_integration(hass, mock_config_entry)
    await _trip_circuit_breaker(hass, mock_pubsub, mock_meshtastic_client)
    async_check_issues(hass, mock_config_entry)
    async_report_unresponsive_node(hass, mock_config_entry, REMOTE_ID)
    async_create_migration_issue(hass, mock_config_entry)

    async_delete_issues(hass, mock_config_entry)

    assert (
        issue_registry.async_get_issue(DOMAIN, _breaker_issue_id(mock_config_entry))
        is None
    )
    assert (
        issue_registry.async_get_issue(
            DOMAIN, _node_issue_id(mock_config_entry, REMOTE_ID)
        )
        is None
    )
    assert (
        issue_registry.async_get_issue(DOMAIN, _migration_issue_id(mock_config_entry))
        is not None
    )


@pytest.mark.parametrize(
    ("issue_id", "known_entry"),
    [
        # The migration issue only has to be acknowledged.
        (f"{ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION}_{{entry_id}}", True),
        # Nothing this module raised.
        ("something_else_{entry_id}", True),
        # The breaker issue of an entry that has since been removed.
        (f"{ISSUE_CIRCUIT_BREAKER_OPEN}_gone", False),
    ],
)
async def test_async_create_fix_flow_falls_back_to_confirm(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_id: str,
    known_entry: bool,
) -> None:
    """Test that anything but a usable breaker issue is only acknowledged."""
    mock_config_entry.add_to_hass(hass)
    entry_id = mock_config_entry.entry_id if known_entry else "gone"

    flow = await async_create_fix_flow(
        hass, issue_id.format(entry_id=entry_id), {ATTR_ENTRY_ID: entry_id}
    )

    assert isinstance(flow, ConfirmRepairFlow)
    assert not isinstance(flow, MeshtasticReconnectRepairFlow)


@pytest.mark.parametrize("data", [None, {}, {ATTR_ENTRY_ID: 1}])
async def test_async_create_fix_flow_without_usable_data(
    hass: HomeAssistant, data: dict[str, str | int | float | None] | None
) -> None:
    """Test a breaker issue whose data does not name a config entry."""
    flow = await async_create_fix_flow(hass, f"{ISSUE_CIRCUIT_BREAKER_OPEN}_abc", data)

    assert isinstance(flow, ConfirmRepairFlow)
    assert not isinstance(flow, MeshtasticReconnectRepairFlow)


async def test_async_create_fix_flow_for_the_circuit_breaker(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the breaker issue gets the reconnecting flow."""
    mock_config_entry.add_to_hass(hass)

    flow = await async_create_fix_flow(
        hass,
        f"{ISSUE_CIRCUIT_BREAKER_OPEN}_{mock_config_entry.entry_id}",
        {ATTR_ENTRY_ID: mock_config_entry.entry_id},
    )

    assert isinstance(flow, MeshtasticReconnectRepairFlow)
    assert flow.entry_id == mock_config_entry.entry_id
