"""Verified alternate hosts learned from reCamera Zeroconf announcements."""

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import CONF_DISCOVERY_CANDIDATES

CANDIDATE_LIMIT = 4
CANDIDATE_TTL = timedelta(days=7)


def _verified_at(value: object) -> datetime | None:
    """Return a normalized candidate verification time."""
    try:
        timestamp = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _normalized_host(value: object) -> str | None:
    """Return a usable host key without changing its address family."""
    host = str(value or "").strip().lower()
    if not host or any(character.isspace() for character in host):
        return None
    return host


def merge_discovery_candidate(
    data: dict[str, Any],
    host: object,
    *,
    now: datetime | None = None,
) -> list[dict[str, str]]:
    """Add one verified host and keep a bounded, deduplicated candidate set."""
    normalized_host = _normalized_host(host)
    if normalized_host is None:
        return _current_candidates(data, now=now)

    now = (now or dt_util.utcnow()).astimezone(UTC)
    candidates: dict[str, datetime] = {
        normalized_host: now,
    }
    for item in _current_candidates(data, now=now):
        candidate_host = _normalized_host(item["host"])
        timestamp = _verified_at(item["verified_at"])
        if candidate_host is None or timestamp is None:
            continue
        existing = candidates.get(candidate_host)
        if existing is None or timestamp > existing:
            candidates[candidate_host] = timestamp

    return [
        {
            "host": candidate_host,
            "verified_at": timestamp.isoformat(),
        }
        for candidate_host, timestamp in sorted(
            candidates.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:CANDIDATE_LIMIT]
    ]


def valid_discovery_candidates(
    data: dict[str, Any],
    current_host: object,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Return unexpired alternate hosts ordered by most recent verification."""
    current = _normalized_host(current_host)
    return [
        item["host"]
        for item in _current_candidates(data, now=now)
        if item["host"] != current
    ]


def recoverable_discovery_candidates(
    data: dict[str, Any],
    current_host: object,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Return alternate hosts that can be safely reauthenticated.

    A seven-day timestamp means "last verified", not "permanently trusted".
    Expired hosts remain safe recovery hints because every switch is followed
    by credential and hardware-identity validation.
    """
    current = _normalized_host(current_host)
    return [
        item["host"]
        for item in _current_candidates(data, now=now, include_expired=True)
        if item["host"] != current
    ]


def drop_discovery_candidate(
    data: dict[str, Any],
    host: object,
) -> list[dict[str, str]]:
    """Remove one rejected host while preserving the remaining candidates."""
    normalized_host = _normalized_host(host)
    return [
        item for item in _current_candidates(data) if item["host"] != normalized_host
    ]


def _current_candidates(
    data: dict[str, Any],
    *,
    now: datetime | None = None,
    include_expired: bool = False,
) -> list[dict[str, str]]:
    """Return valid persisted candidates with invalid entries discarded."""
    now = (now or dt_util.utcnow()).astimezone(UTC)
    candidates: dict[str, datetime] = {}
    raw_candidates = data.get(CONF_DISCOVERY_CANDIDATES)
    if not isinstance(raw_candidates, list):
        return []

    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        host = _normalized_host(item.get("host"))
        verified_at = _verified_at(item.get("verified_at"))
        if host is None or verified_at is None:
            continue
        if not include_expired and now - verified_at > CANDIDATE_TTL:
            continue
        existing = candidates.get(host)
        if existing is None or verified_at > existing:
            candidates[host] = verified_at
    return [
        {
            "host": host,
            "verified_at": verified_at.isoformat(),
        }
        for host, verified_at in sorted(
            candidates.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:CANDIDATE_LIMIT]
    ]
