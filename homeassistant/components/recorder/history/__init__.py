"""Provide pre-made queries on top of the recorder component."""
from __future__ import annotations

from .legacy import (
    get_full_significant_states_with_session,
    get_last_state_changes,
    get_significant_states,
    get_significant_states_with_session,
    state_changes_during_period,
)

# These are the APIs of this package
__all__ = [
    "get_significant_states",
    "get_significant_states_with_session",
    "get_full_significant_states_with_session",
    "state_changes_during_period",
    "get_last_state_changes",
]
