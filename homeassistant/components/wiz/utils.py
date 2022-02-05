"""WiZ utils."""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


def _short_mac(mac: str) -> str:
    """Get the short mac address from the full mac."""
    return mac.replace(":", "").upper()[-6:]
