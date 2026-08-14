"""Constants shared across the JFL Alarm integration.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

Only values that Home Assistant-facing code needs live here. Protocol constants — command bytes,
frame offsets, the model table — belong in the pure `protocol` package.

**This module imports no Home Assistant**, and that is deliberate rather than incidental. The
safety-critical default in it, `DEFAULT_READ_ONLY`, is asserted by a test that has to be able to run
anywhere — including on a machine with no Home Assistant installed. `PLATFORMS` lived here once and
was moved to `__init__.py` for exactly that reason: it was the only thing dragging
`homeassistant.const` in.
"""

from __future__ import annotations

import logging
from typing import Final

# `X as X` is the explicit re-export form. Without it `mypy --strict` refuses every
# `from .const import UNKNOWN_ACCEPT` elsewhere in the integration, because `--strict` turns on
# `no_implicit_reexport`.
from pyjfl import UNKNOWN_ACCEPT as UNKNOWN_ACCEPT
from pyjfl import UNKNOWN_HOLD as UNKNOWN_HOLD
from pyjfl import UNKNOWN_REJECT as UNKNOWN_REJECT

DOMAIN: Final = "jfl_alarm"

LOGGER: Final = logging.getLogger(__package__)

MANUFACTURER: Final = "JFL"

# ------------------------------------------------------------------------------------------------
# Configuration keys
# ------------------------------------------------------------------------------------------------

# The panel dials out to us; we never dial in. This is the port the integration listens on, and the
# port the installer programs into the panel's reporting destination.
#
# **Deliberately not 9090.** That port is crowded — Prometheus, Cockpit and Openfire all want it —
# and this integration is meant to sit beside other software on a machine an installer already uses.
#
# It is *not* avoided because ActiveNet uses it. ActiveNet was observed on 2026-08-08 listening on
# **TCP 2034**, on every interface, with the panel connected to it; 9090 appears in this project's
# older notes as an assumption that was never checked. See `docs/development/lab.md`.
DEFAULT_PORT: Final = 9494

# 0.0.0.0 and not localhost: the panel is a separate box on the LAN, so a listener bound to the
# loopback interface can never be reached by it. This is the single most likely way to end up with
# an integration that starts cleanly and never sees a panel.
DEFAULT_HOST: Final = "0.0.0.0"

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SERIAL: Final = "serial"
CONF_READ_ONLY: Final = "read_only"

# Safety default. This integration controls a real alarm system on an occupied house, so a fresh
# installation observes and does not command until the user opts in. See AGENTS.md §6.
DEFAULT_READ_ONLY: Final = True

# A panel is identified by the 10-byte serial at raw[4:14] of its connection frame, never by the
# config entry id. Entity unique ids are derived from it so they survive a re-add.
SUBENTRY_TYPE_PANEL: Final = "panel"

# ------------------------------------------------------------------------------------------------
# Hub options
# ------------------------------------------------------------------------------------------------

DEFAULT_STATUS_INTERVAL: Final = 30
"""Seconds between `0x4D` status requests. The panel never pushes its status — it only answers a
poll — so it is the only source of zone and partition state. ActiveNet polls about every 12.5 s.
Not user-configurable: a fixed interval that serves the majority of installations."""

CONF_PROGRAMMING_READ_INTERVAL: Final = "programming_read_interval"
"""Minutes between automatic programming reads, or `0` to do it only once per panel.

The programming holds the zone and partition *names*, so before Sprint 8 a freshly added panel
showed `Zone 1`, `Zone 2`, … until somebody found the *Read programming* button. **A panel is now
always read once, automatically, when it first connects** — that is the author's requirement and it
holds even at `0`, which disables only the *repeat*.

A periodic re-read is cheap because it is gated on `KP`, the programming checksum the panel
publishes in every status frame: it changes when, and only when, the programming changes, so a tick
that finds it unchanged sends nothing at all."""

DEFAULT_PROGRAMMING_READ_INTERVAL: Final = 30
MIN_PROGRAMMING_READ_INTERVAL: Final = 0
MAX_PROGRAMMING_READ_INTERVAL: Final = 1440

CONF_KEEPALIVE_MINUTES: Final = "keepalive_minutes"
"""What we tell the panel to use as its keep-alive interval, in the `0x21`/`0x40` reply. 1-20."""

DEFAULT_KEEPALIVE_MINUTES: Final = 5
MIN_KEEPALIVE_MINUTES: Final = 1
MAX_KEEPALIVE_MINUTES: Final = 20

CONF_LOG_RAW_FRAMES: Final = "log_raw_frames"
"""Log every frame's bytes at debug. Off by default: the decoded form is logged either way, and the
hex is only useful when the decoder itself is suspect."""

DEFAULT_LOG_RAW_FRAMES: Final = False

CONF_UNKNOWN_PANELS: Final = "unknown_panels"
"""What to do with a panel that dials in without a matching subentry."""

# The three policy strings are defined by the transport, which is the code that enforces them and
# the half that leaves for `pyjfl` (ADR-0019). They are re-exported here because `const` is where
# the rest of the configuration vocabulary lives and where the config flow looks for it.
UNKNOWN_PANEL_POLICIES: Final = [UNKNOWN_ACCEPT, UNKNOWN_HOLD, UNKNOWN_REJECT]
DEFAULT_UNKNOWN_PANELS: Final = UNKNOWN_ACCEPT

# ------------------------------------------------------------------------------------------------
# Per-panel options
# ------------------------------------------------------------------------------------------------

CONF_ZONE_POLICY: Final = "zone_policy"
"""Which zones become entities."""

ZONES_PROGRAMMED: Final = "programmed"
"""Only zones the panel reports as in use. The right answer for almost everyone."""

ZONES_ALL: Final = "all"
"""Every zone the model can have, including disabled ones. For an installation in progress."""

ZONE_POLICIES: Final = [ZONES_PROGRAMMED, ZONES_ALL]
DEFAULT_ZONE_POLICY: Final = ZONES_PROGRAMMED

CONF_CODE: Final = "code"
"""An **optional** code Home Assistant asks for before arming or disarming.

This is a Home Assistant-side code and has nothing to do with the panel: no user code is ever sent
to the panel, because the command path this integration uses carries no password at all (see
`docs/protocol/commands.md`). It exists so that a tablet on the wall cannot disarm the house with
one tap. Empty means no code, which is the default — the panel's own keypad already has one.

Stored in the panel subentry and treated as a secret: never logged, and redacted in diagnostics.
"""

DEFAULT_CODE: Final = ""

CONF_CODE_ARM_REQUIRED: Final = "code_arm_required"
"""Whether the code is also required to *arm*. Disarming always requires it once a code is set.

Asking on the way out and not on the way in is a normal choice — leaving is routine, and a code the
user is prompted for twenty times a day gets written on the wall next to the tablet.
"""

DEFAULT_CODE_ARM_REQUIRED: Final = True

CONF_FENCE_PGM: Final = "fence_pgm"
"""Which PGM output drives the electric fence, or `0` for "none / I don't know".

⚠️ **The PGM programmed with function 18 switches the energiser.** Toggling it turns the fence off,
so it must never appear as an ordinary output among the lamps and the gate. Naming it here moves
that switch onto the electric fence's own device, in the configuration section, labelled as the
fence's power supply.

**As of Sprint 8 this is an override, not the only source, and as of ADR-0017 setting it is
optional.** A programming read detects the fence's PGM on its own — function 18, or 25 on the Active
20 — and the switch is placed from what was detected, so a panel that never had this set is handled
correctly without anyone being asked to do anything. A value set here still wins over detection,
because the user may know something the programming does not — a relay wired downstream of an output
whose function reads as something else. When the two disagree the setting is honoured and the
disagreement is raised as a repair. See ADR-0011, ADR-0017 and pyjfl's `protocol/capabilities.py`.
"""

DEFAULT_FENCE_PGM: Final = 0
NO_FENCE_PGM: Final = 0

CONF_COMMANDS_ENABLED: Final = "commands_enabled"
"""Restore key for the per-panel master switch that gates every outbound command.

Not a config-entry option: it is a switch entity, so it can be flipped from a dashboard or an
automation without opening the settings. `read_only` is the deliberate opt-in; this is the quick way
to take it back. **Both** have to allow a command before it is sent.
"""

# ------------------------------------------------------------------------------------------------
# Runtime tuning
# ------------------------------------------------------------------------------------------------

PROGRAMMING_READ_FIRST_DELAY: Final = 20.0
"""Seconds to wait before the first automatic programming read of a panel.

Long enough for the panel to have sent its `0x21` introduction and answered one status poll, so the
read starts against a known model rather than the permissive fallback — and short enough that a user
adding a panel sees the real zone names while still looking at the screen."""

PROGRAMMING_READ_IDLE_SLEEP: Final = 3600.0
"""How long the automatic-read loop waits between ticks when the periodic read is switched off.

It still ticks, because the *first* read must happen even at interval `0`; it simply must not spin.
"""

PROGRAMMING_READ_GAP: Final = 0.15
"""Seconds to wait between the requests of a full programming read.

**A full read is thirty-odd round trips on a link that is also carrying the status poll and — on a
Bus panel — the keypad bus.** ActiveNet paced its own reads at roughly this interval. Firing them
back to back would work and would also make the panel's own keypad feel slow to whoever is standing
at it, which is not a trade this integration gets to make on the user's behalf.
"""

PROGRAMMING_READ_RETRIES: Final = 2
"""Attempts per block before a full read gives up on it.

A block that never arrives is one region of the map missing, not a failure of the whole read: the
names of thirty-one zones are worth having while zone 32's request went astray.
"""

VERIFY_DELAYS: Final = (0.6, 2.0)
"""When to re-read the status after sending a command, in seconds.

**The status frame that answers a command is not the final truth.** Arming partition 1 in the
2026-08-08 capture returned a frame that still showed zone 9 open; the panel auto-bypassed it a
second later and announced that only through event `1570`. So one re-read catches the command taking
effect and a second catches whatever the panel decided on its own afterwards.
"""

PANEL_NEVER_CONNECTED_MINUTES: Final = 15
"""How long to wait before telling the user no panel has dialled in. "Nothing appeared" is the
number-one support question for an integration the panel has to connect *to*."""

# ------------------------------------------------------------------------------------------------
# Dispatcher signals and repair issues
# ------------------------------------------------------------------------------------------------


def signal_panel_event(entry_id: str, serial: str) -> str:
    """Return the dispatcher signal carrying Contact ID events for one panel.

    Events do **not** travel in the coordinator snapshot. A snapshot is replayed to every entity on
    every update, so an event stored in one would re-fire on each poll and again on restart — a
    panic button that "presses itself" every thirty seconds. Scoping the signal by entry *and*
    serial keeps two panels, or two config entries, from hearing each other.
    """
    return f"{DOMAIN}_event_{entry_id}_{serial}"


ISSUE_PANEL_NEVER_CONNECTED: Final = "panel_never_connected"
ISSUE_UNSUPPORTED_MODEL: Final = "unsupported_model"
ISSUE_REMOTE_ACCESS_BLOCKED: Final = "remote_access_blocked"
"""Raised on the **first** wrong-password reply, not the fifth. See `repairs.py`."""

ISSUE_FENCE_PGM_DETECTED: Final = "fence_pgm_detected"
"""**Retired by ADR-0017, and kept only so the issue it used to raise can be deleted.**

It asked the user to name an output the integration had *already* identified, in order to fix
placement flags that were decided too early. Now the switch is created from the detected function in
the first place, so there is nothing left to ask for. `repairs.async_check_fence_pgm` deletes any
copy an earlier version raised."""

ISSUE_FENCE_PGM_CONFLICT: Final = "fence_pgm_conflict"
"""Raised when the detected fence PGM disagrees with the one the user configured. The user's setting
is honoured; the disagreement is surfaced because only they can say which is right."""

DEFAULT_EVENT_LIMIT: Final = 200
"""How many buffered events `jfl_alarm.read_event_buffer` returns when the caller names no limit.

The panel's buffer held **1073** records on 2026-08-09 and pages eight at a time, oldest first, so
reading all of it is 135 round trips on a link that is also carrying the status poll. 200 is roughly
a fortnight of an ordinary house and takes about twelve seconds."""

MAX_EVENT_LIMIT: Final = 2000
"""The ceiling the service schema enforces, comfortably above the largest buffer anyone has seen."""

PGM_PLACEMENT_OPTION: Final = "pgm_placement"
"""Entity-registry option marking a PGM switch whose enabled state this integration has settled.

Written once per entity, ever — see `switch._async_settle_existing_row`. It exists because
`entity_registry_enabled_default` is honoured only when a row is *created*, so a row an older
version created enabled would otherwise never learn that its output is unused, while a row the user
enabled by hand must never be disabled again behind their back. The marker separates the two."""

PGM_PLACEMENT_VERSION: Final = 1
"""Bumped only if a future change has to revisit rows this one already settled."""
