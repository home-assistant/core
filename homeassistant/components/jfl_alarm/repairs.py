"""Repair issues — the answers to the two questions this integration will be asked most.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

`panel_never_connected` exists because of the inverted topology. Every other integration a user has
installed connects *out*; this one waits to be connected *to*, and if the installer never programmed
the panel's reporting destination, absolutely nothing happens — no error, no entity, no log line
above debug. "I installed it and nothing appeared" is therefore the number-one support question, and
the answer is a checklist the user can act on rather than a message in a log they will not read.

`unsupported_model` is the honest version of "it seems to work". Only the Active 32 Duo has been
validated on real hardware (AGENTS.md §0), so a panel reporting any other model byte gets a notice
saying which parts are inference, and an unlisted byte gets one saying so outright.

`remote_access_blocked` should never appear. It is raised the first time a panel answers a command
with "wrong password", which nothing this integration sends can provoke — the whole command set runs
on the path that carries no password. It exists because the failure it guards against is one the
user cannot undo from Home Assistant: five wrong passwords block remote operation at the panel until
somebody performs a valid keypad operation. AGENTS.md §6.

`fence_pgm_conflict` is the last of the two issues the fence's PGM used to raise. A PGM on function
18 *is* the energiser's power, and the status frame cannot say so — only the programming can, and
only once it has been read. When the programming and the user's setting name **different** outputs,
one of them is wrong and only the user can say which, so the setting is honoured and the
disagreement is surfaced. ADR-0011.

`fence_pgm_detected` is **gone**, and its removal is worth a note. It fired when a read found an
energiser output the user had never named, and asked them to go and name it — not because the
integration did not know which output it was, but because it had already created that output's
switch with the wrong device, category and enabled flag, and Home Assistant fixes all three when an
entity registers. Asking the user to correct bookkeeping the integration could correct itself is a
repair issue that should never have existed. The switches now wait until the functions are known and
are created in the right place; `async_check_fence_pgm` deletes any copy an earlier version raised.
ADR-0017.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later
from pyjfl import MODELS

from .const import (
    DOMAIN,
    ISSUE_FENCE_PGM_CONFLICT,
    ISSUE_FENCE_PGM_DETECTED,
    ISSUE_PANEL_NEVER_CONNECTED,
    ISSUE_REMOTE_ACCESS_BLOCKED,
    ISSUE_UNSUPPORTED_MODEL,
    LOGGER,
    PANEL_NEVER_CONNECTED_MINUTES,
)

if TYPE_CHECKING:
    from datetime import datetime

    from pyjfl import ConnectionInfo

    from . import JflConfigEntry


@callback
def async_watch_for_silence(hass: HomeAssistant, entry: JflConfigEntry) -> None:
    """Raise an issue if no panel has said anything after a grace period.

    Scheduled once per entry setup. If any panel has connected by the time it fires, nothing
    happens and any previous issue is cleared.
    """

    @callback
    def _check(_now: datetime) -> None:
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None or not runtime.server.is_running:
            return
        if any(link.info is not None for link in runtime.server.links):
            ir.async_delete_issue(hass, DOMAIN, ISSUE_PANEL_NEVER_CONNECTED)
            return
        LOGGER.warning(
            "No JFL panel has connected to %s:%s in %d minutes. Check the panel's reporting "
            "destination and that address 700 TECLA8 dual reporting is enabled",
            runtime.server.host,
            runtime.server.port,
            PANEL_NEVER_CONNECTED_MINUTES,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_PANEL_NEVER_CONNECTED,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_PANEL_NEVER_CONNECTED,
            translation_placeholders={
                "host": runtime.server.host,
                "port": str(runtime.server.port),
                "minutes": str(PANEL_NEVER_CONNECTED_MINUTES),
            },
        )

    entry.async_on_unload(
        async_call_later(hass, PANEL_NEVER_CONNECTED_MINUTES * 60, _check),
    )


@callback
def async_check_model(hass: HomeAssistant, info: ConnectionInfo) -> None:
    """Raise an issue for a panel model nobody has validated against real hardware.

    One issue per serial, so a mixed installation names each panel rather than blurring them into
    a single warning the user cannot act on.
    """
    issue_id = f"{ISSUE_UNSUPPORTED_MODEL}_{info.serial}"
    if info.spec.verified_on_hardware:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    known = info.model_byte in MODELS
    LOGGER.debug(
        "%s: model 0x%02X is %s",
        info.serial,
        info.model_byte,
        "implemented from the specification but untested" if known else "not in the model table",
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_UNSUPPORTED_MODEL if known else "unknown_model",
        translation_placeholders={
            "serial": info.serial,
            "model": info.spec.name,
            "model_byte": f"0x{info.model_byte:02X}",
        },
    )


@callback
def async_check_fence_pgm(
    hass: HomeAssistant, serial: str, *, configured: int, detected: int | None
) -> None:
    """Reconcile the detected fence PGM with the one the user configured, and raise or clear issues.

    Called after every programming read. The three outcomes:

    * **Agreement, or nothing detected** — the setting and the programming say the same thing, or
      the programming names no energiser output. Nothing to warn about.
    * **Detected but not configured** — the ordinary case on a panel nobody has configured, and
      **not a problem**: detection is enough, the switch has already been placed on the fence's
      device from that same reading, and there is nothing for the user to do. Recorded at `debug`.
    * **Detected and configured, but different** — the user's setting is honoured (the coordinator
      never overrides it), and `fence_pgm_conflict` surfaces the disagreement, because one of the
      two is wrong and only the user can say which.

    The issue id is per serial so a mixed installation names each panel. Any `fence_pgm_detected`
    an earlier version raised is deleted here, unconditionally — ADR-0017 retired it.
    """
    detected_id = f"{ISSUE_FENCE_PGM_DETECTED}_{serial}"
    conflict_id = f"{ISSUE_FENCE_PGM_CONFLICT}_{serial}"
    ir.async_delete_issue(hass, DOMAIN, detected_id)

    if detected is None or detected == configured:
        ir.async_delete_issue(hass, DOMAIN, conflict_id)
        return

    if not configured:
        ir.async_delete_issue(hass, DOMAIN, conflict_id)
        LOGGER.debug(
            "%s: PGM %d is programmed to drive the electric fence (address %d); its switch belongs "
            "to the fence's device and is marked as configuration",
            serial,
            detected,
            820 + detected,
        )
        return

    LOGGER.warning(
        "Panel %s: PGM %d is set as the fence's power, but the programming says PGM %d drives it. "
        "The setting is being honoured; check which is correct",
        serial,
        configured,
        detected,
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        conflict_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_FENCE_PGM_CONFLICT,
        translation_placeholders={
            "serial": serial,
            "configured": str(configured),
            "detected": str(detected),
        },
    )


@callback
def async_report_lockout(hass: HomeAssistant, serial: str) -> None:
    """Tell the user a panel rejected a password, and that nothing more will be tried.

    `ERROR`, not `WARNING`: the next four attempts would block remote operation entirely, and the
    only thing that unblocks it is somebody walking to the keypad. This is the one issue in the
    integration that describes damage in progress rather than a setup mistake.
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{ISSUE_REMOTE_ACCESS_BLOCKED}_{serial}",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_REMOTE_ACCESS_BLOCKED,
        translation_placeholders={"serial": serial},
    )
