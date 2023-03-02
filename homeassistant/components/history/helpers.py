"""Helpers for the history integration."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime as dt

from homeassistant.core import HomeAssistant


def entities_may_have_state_changes_after(
    hass: HomeAssistant, entity_ids: Iterable, start_time: dt, no_attributes: bool
) -> bool:
    """Check the state machine to see if entities have changed since start time."""
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None:
            return True

        state_time = state.last_changed if no_attributes else state.last_updated
        if state_time > start_time:
            return True

    return False
