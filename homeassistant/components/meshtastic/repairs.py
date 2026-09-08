"""Repair issues for the Meshtastic integration.

Three things go wrong in a way the user - and only the user - can fix:

* the node accepts a single API client at a time, so a phone app or a CLI
  session left running kicks Home Assistant off over and over until the
  client's circuit breaker gives up;
* a configuration write that reboots a node can leave it not coming back,
  which is a radio or power problem at the far end;
* a config entry inherited from the ``meshtastic`` custom integration keeps
  working, but its entity and device identifiers are this integration's, so
  the old custom component has to be uninstalled by hand.

Issue creation lives here rather than in the modules that detect the
conditions, so that every issue id, severity and placeholder set is written
down once.  Nothing in this module imports the integration package itself, so
``__init__.py`` can import it without a cycle.
"""

from datetime import datetime
from typing import Any, override

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ENTRY_ID,
    ATTR_NODE_ID,
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_TRIPS,
    DOMAIN,
)
from .coordinator import MeshtasticConfigEntry
from .models import ConnectionState

#: Home Assistant keeps being kicked off the node by another API client.
ISSUE_CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
#: A node never came back from a write that reboots it.
ISSUE_NODE_UNRESPONSIVE = "node_unresponsive"
#: The entry was inherited from the HACS custom integration.
ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION = "migrated_from_custom_integration"

#: Key under which the unresponsive-node issue records when it was raised, so
#: that hearing from the node again clears it.
ATTR_NOTICED_AT = "noticed_at"


def _breaker_issue_id(entry_id: str) -> str:
    """Return the issue id of the circuit-breaker issue of one entry."""
    return f"{ISSUE_CIRCUIT_BREAKER_OPEN}_{entry_id}"


def _migration_issue_id(entry_id: str) -> str:
    """Return the issue id of the migration issue of one entry."""
    return f"{ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION}_{entry_id}"


def _node_issue_prefix(entry_id: str) -> str:
    """Return the common prefix of the unresponsive-node issues of one entry."""
    return f"{ISSUE_NODE_UNRESPONSIVE}_{entry_id}_"


def _node_issue_id(entry_id: str, node_id: str) -> str:
    """Return the issue id of the unresponsive-node issue of one node."""
    return f"{_node_issue_prefix(entry_id)}{node_id}"


@callback
def async_check_issues(hass: HomeAssistant, entry: MeshtasticConfigEntry) -> None:
    """Reconcile the issues that follow from the entry's live state.

    Cheap and idempotent: call it whenever the link state or the node table
    changed.  It both raises and withdraws issues, so a node that comes back or
    a competing client that goes away resolves the repair on its own.
    """
    _async_check_circuit_breaker(hass, entry)
    _async_check_unresponsive_nodes(hass, entry)


@callback
def _async_check_circuit_breaker(
    hass: HomeAssistant, entry: MeshtasticConfigEntry
) -> None:
    """Raise or withdraw the "another client keeps kicking us" issue."""
    client = entry.runtime_data.client
    issue_id = _breaker_issue_id(entry.entry_id)
    stats = client.stats()
    if not (
        stats["circuit_breaker_open"]
        or client.connection_state is ConnectionState.CIRCUIT_OPEN
    ):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        data={ATTR_ENTRY_ID: entry.entry_id},
        is_fixable=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_CIRCUIT_BREAKER_OPEN,
        translation_placeholders={
            "name": entry.title,
            "host": entry.data[CONF_HOST],
            "count": str(CIRCUIT_BREAKER_TRIPS),
            "seconds": str(int(CIRCUIT_BREAKER_COOLDOWN)),
        },
    )


@callback
def _async_check_unresponsive_nodes(
    hass: HomeAssistant, entry: MeshtasticConfigEntry
) -> None:
    """Withdraw unresponsive-node issues for nodes that have been heard since."""
    coordinator = entry.runtime_data.coordinator
    registry = ir.async_get(hass)
    prefix = _node_issue_prefix(entry.entry_id)
    for domain, issue_id in list(registry.issues):
        if domain != DOMAIN or not issue_id.startswith(prefix):
            continue
        data = registry.issues[domain, issue_id].data or {}
        node = coordinator.get_node(str(data.get(ATTR_NODE_ID)))
        noticed_at = _parse_noticed_at(data.get(ATTR_NOTICED_AT))
        if (
            node is not None
            and node.last_heard is not None
            and noticed_at is not None
            and node.last_heard > noticed_at
        ):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


def _parse_noticed_at(value: Any) -> datetime | None:
    """Return the recorded detection time of an issue, if it is readable."""
    if not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


@callback
def async_report_unresponsive_node(
    hass: HomeAssistant, entry: MeshtasticConfigEntry, node_id: str
) -> None:
    """Report that a node never came back from a write that reboots it.

    Call this once the reboot grace window elapsed without hearing from the
    node.  The issue withdraws itself as soon as the node is heard again.
    """
    node = entry.runtime_data.coordinator.get_node(node_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        _node_issue_id(entry.entry_id, node_id),
        data={
            ATTR_ENTRY_ID: entry.entry_id,
            ATTR_NODE_ID: node_id,
            ATTR_NOTICED_AT: dt_util.utcnow().isoformat(),
        },
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_NODE_UNRESPONSIVE,
        translation_placeholders={
            "name": node_id if node is None else node.name,
            "node_id": node_id,
            "gateway": entry.title,
        },
    )


@callback
def async_create_migration_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Report that this entry was inherited from the custom integration.

    Persistent, because the migration itself runs exactly once: the user has to
    see this even if it happened during a restart they did not watch.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        _migration_issue_id(entry.entry_id),
        data={ATTR_ENTRY_ID: entry.entry_id},
        is_fixable=True,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION,
        translation_placeholders={
            "name": entry.title,
            "host": str(entry.data.get(CONF_HOST, "")),
        },
    )


@callback
def async_delete_issues(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Withdraw the live issues of one entry, on unload or removal.

    The migration issue is deliberately kept: it describes something the user
    still has to do outside Home Assistant.
    """
    ir.async_delete_issue(hass, DOMAIN, _breaker_issue_id(entry.entry_id))
    registry = ir.async_get(hass)
    prefix = _node_issue_prefix(entry.entry_id)
    for domain, issue_id in list(registry.issues):
        if domain == DOMAIN and issue_id.startswith(prefix):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


class MeshtasticReconnectRepairFlow(ConfirmRepairFlow):
    """Confirm the competing client is gone and reconnect straight away."""

    def __init__(self, entry_id: str) -> None:
        """Initialise the flow for one config entry."""
        self.entry_id = entry_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Reload the entry, which drops the cooldown and reconnects now."""
        if user_input is not None:
            self.hass.config_entries.async_schedule_reload(self.entry_id)
        return await super().async_step_confirm(user_input)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for one issue."""
    if (
        issue_id.startswith(f"{ISSUE_CIRCUIT_BREAKER_OPEN}_")
        and data is not None
        and isinstance(entry_id := data.get(ATTR_ENTRY_ID), str)
        # The entry can be gone by the time the user gets to the repair, and
        # reloading an entry that no longer exists raises.
        and hass.config_entries.async_get_entry(entry_id) is not None
    ):
        return MeshtasticReconnectRepairFlow(entry_id)
    # The migration issue only has to be acknowledged.
    return ConfirmRepairFlow()
