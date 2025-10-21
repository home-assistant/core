"""Library-shared protocol helpers for Level Lock.

Pure helper module to avoid circular imports.
"""

from __future__ import annotations

from typing import Any


def coerce_is_locked(state: Any) -> bool | None:
    """Convert vendor state to boolean locked status or None for unknown.

    Transitional states (e.g., "locking"/"unlocking") return None.
    """

    if state is None:
        return None
    if isinstance(state, str):
        lowered = state.lower()
        if lowered in ("locked", "lock", "secure"):
            return True
        if lowered in ("unlocked", "unlock", "unsecure"):
            return False
        if lowered in ("locking", "unlocking"):
            return None
    if isinstance(state, bool):
        return state
    return None


