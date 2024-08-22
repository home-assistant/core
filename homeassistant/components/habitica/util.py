"""Utility functions for Habitica."""

from __future__ import annotations

import datetime
from typing import Any

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def next_due_date(task: dict[str, Any], last_cron: str) -> datetime.date | None:
    """Calculate due date for dailies and yesterdailies."""

    if task["isDue"] and not task["completed"]:
        return dt_util.as_local(datetime.datetime.fromisoformat(last_cron)).date()
    try:
        return dt_util.as_local(
            datetime.datetime.fromisoformat(task["nextDue"][0])
        ).date()
    except ValueError:
        # sometimes nextDue dates are in this format instead of iso:
        # "Mon May 06 2024 00:00:00 GMT+0200"
        try:
            return dt_util.as_local(
                datetime.datetime.strptime(
                    task["nextDue"][0], "%a %b %d %Y %H:%M:%S %Z%z"
                )
            ).date()
        except ValueError:
            return None
    except IndexError:
        return None


def entity_used_in(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Get list of related automations and scripts."""
    used_in = automations_with_entity(hass, entity_id)
    used_in += scripts_with_entity(hass, entity_id)
    return used_in
