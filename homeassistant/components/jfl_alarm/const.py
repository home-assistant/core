"""Constants for the JFL Alarm integration."""

import logging
from typing import Final

from pyjfl import UNKNOWN_ACCEPT

DOMAIN: Final = "jfl_alarm"

LOGGER: Final = logging.getLogger(__package__)

MANUFACTURER: Final = "JFL"

# The port the integration listens on, and the port the installer programs into the panel's
# reporting destination. Deliberately not 9090, which Prometheus, Cockpit and Openfire all want.
DEFAULT_PORT: Final = 9494

# The panel is a separate box on the LAN, so a listener bound to loopback can never be reached.
DEFAULT_HOST: Final = "0.0.0.0"

CONF_SERIAL: Final = "serial"
CONF_READ_ONLY: Final = "read_only"

# Safety default: a fresh installation observes and does not command until the user opts in.
DEFAULT_READ_ONLY: Final = True

SUBENTRY_TYPE_PANEL: Final = "panel"

DEFAULT_STATUS_INTERVAL: Final = 30
"""Seconds between `0x4D` status requests. The panel never pushes its status, so a poll is the only
source of zone and partition state."""

DEFAULT_PROGRAMMING_READ_INTERVAL: Final = 30
"""Minutes between programming reads, which is where the zone and partition names come from.

A re-read is cheap because it is gated on `KP`, the programming checksum in every status frame: a
tick that finds it unchanged sends nothing at all.
"""

DEFAULT_KEEPALIVE_MINUTES: Final = 5
"""What the panel is told to use as its keep-alive interval, in the `0x21`/`0x40` reply."""

DEFAULT_LOG_RAW_FRAMES: Final = False
"""Whether to log every frame's bytes at debug. The decoded form is logged either way."""

DEFAULT_UNKNOWN_PANELS: Final = UNKNOWN_ACCEPT
"""What to do with a panel that dials in without a matching subentry."""

DEFAULT_CODE: Final = ""
"""`CONF_CODE` is an optional Home Assistant code asked for before arming or disarming.

It never reaches the panel: the command path this integration uses carries no password at all. It
exists so that a tablet on the wall cannot disarm the house with one tap.
"""

CONF_CODE_ARM_REQUIRED: Final = "code_arm_required"
"""Whether the code is also required to arm. Disarming always requires it once a code is set."""

DEFAULT_CODE_ARM_REQUIRED: Final = True

PROGRAMMING_READ_FIRST_DELAY: Final = 20.0
"""Seconds before the first programming read, so that it starts against a known model."""

PROGRAMMING_READ_IDLE_SLEEP: Final = 3600.0
"""How long the read loop waits between ticks when the periodic read is switched off."""

PROGRAMMING_READ_GAP: Final = 0.15
"""Seconds between the requests of a full read, which is thirty-odd round trips on a link that is
also carrying the status poll and the keypad bus."""

PROGRAMMING_READ_RETRIES: Final = 2
"""Attempts per block before a full read gives up on it. A block that never arrives is one region
of the map missing, not a failure of the whole read."""

VERIFY_DELAYS: Final = (0.6, 2.0)
"""When to re-read the status after sending a command, in seconds.

The status frame that answers a command is not the final truth: arming a partition can return a
frame that still shows a zone open, which the panel then auto-bypasses a second later.
"""


def signal_panel_event(entry_id: str, serial: str) -> str:
    """Return the dispatcher signal carrying Contact ID events for one panel.

    Events do not travel in the coordinator snapshot: a snapshot is replayed to every entity on
    every update, so an event stored in one would re-fire on each poll and again on restart.
    """
    return f"{DOMAIN}_event_{entry_id}_{serial}"
