"""Pure detection state for YOLO and sound observations."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from recamera_protocol import ResultObservation

SOURCE_AVAILABLE = "available"
SOURCE_UNKNOWN = "unknown"
SOURCE_UNAVAILABLE = "unavailable"

SUMMARY_CLASS_SWITCH_SECONDS = 1.0
SUMMARY_CONFIDENCE_DELTA = 0.05
SUMMARY_CONFIDENCE_INTERVAL = 5.0
CONFIRM_CANDIDATE_GAP_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class EventRecord:
    """One accepted YOLO event edge."""

    serial: int
    observation: ResultObservation
    context: object | None = None


@dataclass(slots=True)
class DetectionState:
    """Health, active holds, and event history for builtin YOLO."""

    health: str = SOURCE_UNKNOWN
    reason: str | None = None
    last_received: datetime | None = None
    last_received_monotonic: float | None = None
    last_observation: ResultObservation | None = None
    summary_observation: ResultObservation | None = None
    summary_candidate_key: str | None = None
    summary_candidate_since: float | None = None
    summary_updated_monotonic: float | None = None
    active_classes: set[str] = field(default_factory=set)
    class_last_seen: dict[str, float] = field(default_factory=dict)
    confirm_candidate_since: dict[str, float] = field(default_factory=dict)
    confirm_candidate_last_seen: dict[str, float] = field(default_factory=dict)
    cooldown_until: dict[str, float] = field(default_factory=dict)
    event_serial: int = 0
    events: tuple[EventRecord, ...] = ()
    clock_invalid: bool = False

    @property
    def last_event(self) -> ResultObservation | None:
        """Return the latest accepted YOLO event."""
        return self.events[-1].observation if self.events else None


def family_is_available(state: DetectionState) -> bool:
    """Return whether builtin YOLO has usable evidence."""
    return state.health == SOURCE_AVAILABLE


def source_is_available(state: DetectionState) -> bool:
    """Return whether builtin YOLO has usable evidence."""
    return state.health == SOURCE_AVAILABLE


def update_source_observations(
    state: DetectionState,
    observations: list[ResultObservation],
    *,
    received_at: datetime,
    monotonic_now: float,
    confidence_threshold: float,
    confirm_seconds: float = 0.0,
    cooldown_seconds: float,
    next_event_serial: int,
    history_limit: int,
) -> tuple[DetectionState, tuple[EventRecord, ...], int]:
    """Apply one YOLO frame and return accepted entered-class events."""
    active = set(state.active_classes)
    last_seen = dict(state.class_last_seen)
    confirm_since = dict(state.confirm_candidate_since)
    confirm_last_seen = dict(state.confirm_candidate_last_seen)
    cooldown_until = dict(state.cooldown_until)
    eligible: dict[str, ResultObservation] = {}
    for observation in observations:
        if observation.confidence < confidence_threshold:
            continue
        current = eligible.get(observation.class_key)
        if current is None or observation.confidence > current.confidence:
            eligible[observation.class_key] = observation

    for identity, last_candidate_seen in list(confirm_last_seen.items()):
        if (
            identity not in eligible
            and monotonic_now - last_candidate_seen > CONFIRM_CANDIDATE_GAP_SECONDS
        ):
            confirm_since.pop(identity, None)
            confirm_last_seen.pop(identity, None)

    confirmed: dict[str, ResultObservation] = {}
    for identity, observation in eligible.items():
        if identity in active:
            last_seen[identity] = monotonic_now
            confirm_since.pop(identity, None)
            confirm_last_seen.pop(identity, None)
            continue
        if confirm_seconds <= 0:
            active.add(identity)
            last_seen[identity] = monotonic_now
            confirmed[identity] = observation
            continue
        confirm_since.setdefault(identity, monotonic_now)
        confirm_last_seen[identity] = monotonic_now
        if monotonic_now - confirm_since[identity] >= confirm_seconds:
            active.add(identity)
            last_seen[identity] = monotonic_now
            confirmed[identity] = observation
            confirm_since.pop(identity, None)
            confirm_last_seen.pop(identity, None)

    new_records: list[EventRecord] = []
    for observation in sorted(
        (
            observation
            for identity, observation in confirmed.items()
            if monotonic_now >= cooldown_until.get(identity, 0.0)
        ),
        key=lambda item: item.confidence,
        reverse=True,
    ):
        next_event_serial += 1
        new_records.append(EventRecord(next_event_serial, observation))
        cooldown_until[observation.class_key] = monotonic_now + cooldown_seconds

    frame_observation = (
        max(eligible.values(), key=lambda item: item.confidence) if eligible else None
    )
    latest_observation = frame_observation or state.last_observation
    summary = state.summary_observation or state.last_observation
    candidate_key: str | None = None
    candidate_since: float | None = None
    summary_updated = state.summary_updated_monotonic

    if summary is None and frame_observation is not None:
        summary = frame_observation
        summary_updated = monotonic_now
    elif frame_observation is None or summary is None:
        candidate_key = None
        candidate_since = None
    elif summary.class_key == frame_observation.class_key:
        if summary_updated is None or (
            monotonic_now - summary_updated >= SUMMARY_CONFIDENCE_INTERVAL
            and abs(frame_observation.confidence - summary.confidence)
            >= SUMMARY_CONFIDENCE_DELTA
        ):
            summary = frame_observation
            summary_updated = monotonic_now
    elif (
        state.summary_candidate_key != frame_observation.class_key
        or state.summary_candidate_since is None
    ):
        candidate_key = frame_observation.class_key
        candidate_since = monotonic_now
    elif monotonic_now - state.summary_candidate_since >= SUMMARY_CLASS_SWITCH_SECONDS:
        summary = frame_observation
        summary_updated = monotonic_now
    else:
        candidate_key = state.summary_candidate_key
        candidate_since = state.summary_candidate_since

    updated = replace(
        state,
        health=SOURCE_AVAILABLE,
        reason=None,
        last_received=received_at,
        last_received_monotonic=monotonic_now,
        last_observation=latest_observation,
        summary_observation=summary,
        summary_candidate_key=candidate_key,
        summary_candidate_since=candidate_since,
        summary_updated_monotonic=summary_updated,
        active_classes=active,
        class_last_seen=last_seen,
        confirm_candidate_since=confirm_since,
        confirm_candidate_last_seen=confirm_last_seen,
        cooldown_until=cooldown_until,
        event_serial=next_event_serial if new_records else state.event_serial,
        events=(state.events + tuple(new_records))[-history_limit:],
        clock_invalid=(
            any(not item.clock_valid for item in observations)
            if observations
            else state.clock_invalid
        ),
    )
    return updated, tuple(new_records), next_event_serial


def update_source_health(
    state: DetectionState,
    *,
    health: str,
    reason: str | None,
    received_at: datetime,
    monotonic_now: float,
) -> DetectionState:
    """Apply builtin source health without deleting event history."""
    return replace(
        state,
        health=health,
        reason=reason,
        last_received=received_at,
        last_received_monotonic=monotonic_now,
        active_classes=(
            set(state.active_classes) if health == SOURCE_AVAILABLE else set()
        ),
        class_last_seen=(
            dict(state.class_last_seen) if health == SOURCE_AVAILABLE else {}
        ),
        confirm_candidate_since=(
            dict(state.confirm_candidate_since) if health == SOURCE_AVAILABLE else {}
        ),
        confirm_candidate_last_seen=(
            dict(state.confirm_candidate_last_seen)
            if health == SOURCE_AVAILABLE
            else {}
        ),
    )


def expire_detection_state(
    state: DetectionState,
    *,
    now_monotonic: float,
    stale_seconds: float,
    source_offline_seconds: float,
    websocket_connected: bool,
) -> tuple[DetectionState, bool]:
    """Expire held detections and mark a silent stream unknown."""
    stale_keys = {
        identity
        for identity, last_seen in state.class_last_seen.items()
        if now_monotonic - last_seen > stale_seconds
    }
    changed = bool(stale_keys)
    active = set(state.active_classes)
    last_seen = dict(state.class_last_seen)
    candidate_since = dict(state.confirm_candidate_since)
    candidate_last_seen = dict(state.confirm_candidate_last_seen)
    for identity in stale_keys:
        active.discard(identity)
        last_seen.pop(identity, None)

    stale_candidates = {
        identity
        for identity, last_seen_at in candidate_last_seen.items()
        if now_monotonic - last_seen_at > CONFIRM_CANDIDATE_GAP_SECONDS
    }
    for identity in stale_candidates:
        candidate_since.pop(identity, None)
        candidate_last_seen.pop(identity, None)
    changed = changed or bool(stale_candidates)

    health = state.health
    reason = state.reason
    if (
        websocket_connected
        and state.last_received_monotonic is not None
        and now_monotonic - state.last_received_monotonic > source_offline_seconds
        and health == SOURCE_AVAILABLE
    ):
        health = SOURCE_UNKNOWN
        reason = "no_recent_frames"
        active.clear()
        last_seen.clear()
        candidate_since.clear()
        candidate_last_seen.clear()
        changed = True

    if not changed:
        return state, False
    return (
        replace(
            state,
            health=health,
            reason=reason,
            active_classes=active,
            class_last_seen=last_seen,
            confirm_candidate_since=candidate_since,
            confirm_candidate_last_seen=candidate_last_seen,
        ),
        True,
    )
