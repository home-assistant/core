"""Patch time related functions."""

from __future__ import annotations

import datetime

from homeassistant import util
from homeassistant.helpers import event as event_helper
from homeassistant.util import dt as dt_util


def _utcnow() -> datetime.datetime:
    """Make utcnow patchable by freezegun."""
    return datetime.datetime.now(datetime.UTC)


# Replace partial functions which are not found by freezegun
dt_util.utcnow = _utcnow  # type: ignore[assignment]
event_helper.time_tracker_utcnow = _utcnow  # type: ignore[assignment]
util.utcnow = _utcnow  # type: ignore[assignment]
