"""Constants for the Habitron integration.

Protocol indices, module codes and event ids now live in the
``habitron_client`` library (the integration is a thin wrapper). Only the
integration-level constants (domain, service keys, heartbeat interval) remain
here.
"""

from datetime import timedelta
import re
from typing import Final

DOMAIN = "habitron"
CONF_DEFAULT_HOST = "local"  # default host string of SmartCenter, uses own ip

# Heartbeat interval used by the coordinator. Not user-configurable per
# Home Assistant integration guidelines — each poll is CRC-deduplicated and the
# parser fires per-member listeners only on an actual change, so a fixed
# interval is the right shape.
SCAN_INTERVAL: Final = timedelta(seconds=10)

# A hub's identity is its MAC, written bare and lower case -- the custom (HACS)
# integration derives it the same way, so both recognise the same entry.
_MAC_RE: Final = re.compile(r"[0-9a-f]{12}")
# Shape alone is not enough: the all-zero address is what this integration
# starts out with before a hub has answered, and the broadcast address is not
# a machine either. Both pass the pattern and would be shared by every hub
# reporting them.
_NOT_AN_IDENTITY: Final = frozenset({"000000000000", "ffffffffffff"})


def normalised_mac(value: str) -> str | None:
    """Return ``value`` as a bare lower-case MAC, or ``None`` if it is not one.

    Only a real address may become an identity. A hub that sends something
    else -- an IP, a redaction, a placeholder its firmware falls back to --
    would otherwise hand out a unique_id that two machines could share.
    """
    mac = value.replace(":", "").replace("-", "").casefold()
    if not _MAC_RE.fullmatch(mac) or mac in _NOT_AN_IDENTITY:
        return None
    return mac
