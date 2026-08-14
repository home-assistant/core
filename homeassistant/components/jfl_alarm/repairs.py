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
"""

from typing import TYPE_CHECKING

from pyjfl import MODELS

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
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
        "implemented from the specification but untested"
        if known
        else "not in the model table",
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
