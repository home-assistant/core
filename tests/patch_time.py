"""Patch time related functions."""

import datetime
import time
import types
from typing import Any

import freezegun


def ha_datetime_to_fakedatetime(datetime) -> freezegun.api.FakeDatetime:  # type: ignore[name-defined]
    """Convert datetime to FakeDatetime.

    Modified to include https://github.com/spulec/freezegun/pull/424.
    """
    return freezegun.api.FakeDatetime(  # type: ignore[attr-defined]
        datetime.year,
        datetime.month,
        datetime.day,
        datetime.hour,
        datetime.minute,
        datetime.second,
        datetime.microsecond,
        datetime.tzinfo,
        fold=datetime.fold,
    )


def ha_get_module_attributes(module: types.ModuleType) -> list[tuple[str, Any]]:
    """Return the attributes of a module.

    Modified to only look at attributes which are already set, instead of every
    name dir() offers. Packages with a lazy __getattr__, such as scipy or
    elevenlabs, import their whole tree when each name is read, which takes
    seconds and is charged to whichever test freezes time next.
    """
    return list(getattr(module, "__dict__", {}).items())


def ha_get_module_attributes_hash(module: types.ModuleType) -> str:
    """Return a hash of the module attributes.

    Modified to hash the same namespace ha_get_module_attributes reads, so that
    a module which grows an attribute after it was first scanned is scanned
    again. dir() does not report such a change for lazy modules.
    """
    return f"{id(module)}-{hash(frozenset(getattr(module, '__dict__', {})))}"


class HAFakeDateMeta(freezegun.api.FakeDateMeta):
    """Modified to override the string representation."""

    def __str__(cls) -> str:  # noqa: N805 (ruff doesn't know this is a metaclass)
        """Return the string representation of the class."""
        return "<class 'datetime.date'>"


class HAFakeDate(freezegun.api.FakeDate, metaclass=HAFakeDateMeta):  # type: ignore[name-defined]
    """Modified to improve class str."""


class HAFakeDatetimeMeta(freezegun.api.FakeDatetimeMeta):
    """Modified to override the string representation."""

    def __str__(cls) -> str:  # noqa: N805 (ruff doesn't know this is a metaclass)
        """Return the string representation of the class."""
        return "<class 'datetime.datetime'>"


class HAFakeDatetime(freezegun.api.FakeDatetime, metaclass=HAFakeDatetimeMeta):  # type: ignore[name-defined]
    """Modified to include basic fold support and improve class str.

    Fold support submitted to upstream in https://github.com/spulec/freezegun/pull/424.
    """

    @classmethod
    def now(cls, tz=None):
        """Return frozen now."""
        now = cls._time_to_freeze() or freezegun.api.real_datetime.now()
        if tz:
            result = tz.fromutc(now.replace(tzinfo=tz))
        else:
            result = now

        # Add the _tz_offset only if it's non-zero to preserve fold
        if cls._tz_offset():
            result += cls._tz_offset()

        return ha_datetime_to_fakedatetime(result)


# Needed by Mashumaro
datetime.HAFakeDatetime = HAFakeDatetime

# Do not add any Home Assistant import here


def _utcnow() -> datetime.datetime:
    """Make utcnow patchable by freezegun."""
    return datetime.datetime.now(datetime.UTC)  # pylint: disable=home-assistant-enforce-utcnow


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
