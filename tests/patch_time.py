"""Patch time related functions."""

from __future__ import annotations

import datetime
import time

from homeassistant import util


def _utcnow() -> datetime.datetime:
    """Make utcnow patchable by freezegun."""
    return datetime.datetime.now(datetime.UTC)


def _monotonic() -> float:
    """Make monotonic patchable by freezegun."""
    return time.monotonic()


# Before importing anything else, replace partial utcnow
# with a regular function which can be found by freezegun
util.utcnow = util.dt.utcnow = _utcnow  # type: ignore[assignment]


# Replace partial functions which are not found by freezegun
from homeassistant import runner  # noqa: E402
from homeassistant.helpers import event as event_helper  # noqa: E402

# Replace partial functions which are not found by freezegun
event_helper.time_tracker_utcnow = _utcnow  # type: ignore[assignment]
runner.monotonic = _monotonic  # type: ignore[assignment]
