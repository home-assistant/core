"""Patch time related functions."""

from __future__ import annotations

import datetime
import time

# Do not add any Home Assistant import here


def _utcnow() -> datetime.datetime:
    """Make utcnow patchable by freezegun."""
    return datetime.datetime.now(datetime.UTC)


def _monotonic() -> float:
    """Make monotonic patchable by freezegun."""
    return time.monotonic()


# Before importing any other Home Assistant functionality, import and replace
# partial dt_util.utcnow with a regular function which can be found by freezegun
from homeassistant import util  # noqa: E402
from homeassistant.util import dt as dt_util  # noqa: E402

dt_util.utcnow = _utcnow  # type: ignore[assignment]
util.utcnow = _utcnow  # type: ignore[assignment]


# Import other Home Assistant functionality which we need to patch
from homeassistant import runner  # noqa: E402
from homeassistant.helpers import event as event_helper  # noqa: E402

# Replace partial functions which are not found by freezegun
event_helper.time_tracker_utcnow = _utcnow  # type: ignore[assignment]

# Replace bound methods which are not found by freezegun
runner.monotonic = _monotonic  # type: ignore[assignment]
