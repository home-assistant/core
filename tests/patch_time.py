"""Patch time related functions."""
from __future__ import annotations

import datetime

from homeassistant import util
from homeassistant.util import dt as dt_util


def _utcnow() -> datetime.datetime:
    """Make utcnow patchable by freezegun."""
    return datetime.datetime.now(datetime.UTC)


dt_util.utcnow = _utcnow  # type: ignore[assignment]
util.utcnow = _utcnow  # type: ignore[assignment]
