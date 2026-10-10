"""Repair issues for the Meshtastic integration.

Two things go wrong in a way the user - and only the user - can fix:

* the node accepts a single API client at a time, so a phone app or a CLI
  session left running kicks Home Assistant off over and over until the
  client's circuit breaker gives up;
* a config entry inherited from the ``meshtastic`` custom integration keeps
  working, but its entity and device identifiers are this integration's, so
  the old custom component has to be uninstalled by hand.

Issue creation lives here rather than in the modules that detect the
conditions, so that every issue id, severity and placeholder set is written
down once.  Nothing in this module imports the integration package itself, so
``__init__.py`` can import it without a cycle.
"""

from typing import override

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import (
    ATTR_ENTRY_ID,
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_TRIPS,
    DOMAIN,
)
from .coordinator import MeshtasticConfigEntry
from .models import ConnectionState

#: Home Assistant keeps being kicked off the node by another API client.
ISSUE_CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
#: The entry was inherited from the HACS custom integration.
ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION = "migrated_from_custom_integration"


def _breaker_issue_id(entry_id: str) -> str:
    """Return the issue id of the circuit-breaker issue of one entry."""
    return f"{ISSUE_CIRCUIT_BREAKER_OPEN}_{entry_id}"


def _migration_issue_id(entry_id: str) -> str:
    """Return the issue id of the migration issue of one entry."""
    return f"{ISSUE_MIGRATED_FROM_CUSTOM_INTEGRATION}_{entry_id}"


@callback
def async_check_issues(hass: HomeAssistant, entry: MeshtasticConfigEntry) -> None:
    """Raise or withdraw the "another client keeps kicking us" issue.

    Cheap and idempotent: call it whenever the link state changed.  It both
    raises and withdraws, so a competing client that goes away resolves the
    repair on its own.
    """
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
