"""Per-camera live-session bookkeeping.

Phase 1 of the coordinator god-object rewrite (see
.claude/plans/jiggly-moseying-peacock.md, in the project root). Consolidates
per-camera coordinator dicts into one object per camera.

Slice 1 folded in three dicts with NO external readers (only
`BoschCameraCoordinator` itself, in ``__init__.py``, ever touched them):
``_auto_renew_generation``, ``_session_idle_since``, ``_stream_warming_started``.

Slice 2 (this one) folds in two more: ``_stream_warming`` (a ``set[str]``)
and ``_live_opened_at`` (a ``dict[str, float]``) — both DO have external
readers (``camera.py``: ``in``/``not in`` on ``_stream_warming``, ``.get()``/
``.pop()`` on ``_live_opened_at``). Rather than rewrite those call sites,
``_StreamWarmingView``/``_LiveOpenedAtView`` below are thin facades
implementing exactly the subset of the ``set``/``dict`` protocol those call
sites use, backed by the same ``_sessions`` store — so
``coordinator.stream_warming``/``coordinator.live_opened_at`` keep
behaving exactly as before to every external caller, with zero changes
needed in ``camera.py``/``switch.py``.

Deliberately NOT folded into Slice 2: ``_live_connections`` itself — a much
larger, heterogeneous ~15-key dict (raw Bosch API JSON plus derived fields)
with real external MUTATION (multiple ``.pop()`` call sites across
``camera.py``/``switch.py``/``stream_lifecycle.py``/``live_connection.py``),
not just reads. That merge needed its own dedicated design and was folded
in later, in Slice 3 (see below) — `CacheFieldView` turned out to be
sufficient after all (verified via a dedicated `.pop()`-semantics test
before relying on it), since it is already a full `MutableMapping`.

Slice 1 of the ``docs/stream-perf-stability-refactor-plan.md`` "Session-
State-Facade — inkrementeller Migrationsplan" (Anhang 2026-07-13) folds in
the diagnostic/write-lock timestamp fields: ``offline_seen_at`` and every
``*_set_at`` write-lock timestamp (13 of them — one per cloud-writable
field guarded by ``BoschCameraCoordinator.is_write_locked``), plus three
boolean "already logged/deferred this cycle" flags
(``notif_disabled_logged``, ``fw_update_alerted``, ``slow_tier_deferred``).
Generalizes the ``LiveOpenedAtView``/``StreamWarmingView`` pattern above
into reusable ``FloatFieldView``/``BoolFieldView`` classes parameterized by
field name, since Slice 1 has 14 float fields and 3 bool fields rather than
one each — a hand-rolled view class per field would be pure duplication.
External call sites (``shc.py``, ``switch.py``, ``select.py``, ``light.py``,
``number.py``, ``services.py``, ``slow_tier.py``) keep using
``coordinator._x_set_at.get()``/``[cam_id] = ...`` / ``in``/``.add()``/
``.discard()`` exactly as before — only the ``__init__.py`` declaration
changed from a bare ``dict``/``set`` to a view instance.

``generation`` is the TOCTOU guard central to this rewrite's motivation: a
caller that decides to tear down or renew a session captures the generation
at decision time, and re-checks it after any ``await`` (lock acquisition,
sleep) before acting — a generation mismatch means a newer session has
since superseded the stale decision.

Slice 2 of the ``docs/stream-perf-stability-refactor-plan.md`` "Session-
State-Facade — inkrementeller Migrationsplan" folds in 27 per-cam_id cache
fields with no cross-camera access: every ``_rcp_*_cache`` (RCP protocol
data — dimmer/privacy/clock-offset/lan-ip/product-name/bitrate/alarm-
catalog/motion-zones/motion-coords/tls-cert/network-services/iva-catalog/
onvif-scopes/version/state), ``_shc_state_cache``, ``_pan_cache``,
``_audio_cache``, ``_local_creds_cache``, ``_nvr_mode_preference``, and the
plain per-cam Mini-NVR status dicts ``_nvr_user_intent``/``_nvr_error_state``/
``_nvr_recent_crash``/``_nvr_auth_retry_count``/``_nvr_event_clip_enabled``/
``_nvr_preroll_last_crash``/``_nvr_preroll_segment_counts``. Unlike Slice 1's
float/bool fields, these are heterogeneous (dict/list/int/str/float/bool,
several themselves ``Optional``) — generalized into one generic
``CacheFieldView[_T]`` built on ``collections.abc.MutableMapping`` rather
than one hand-rolled view class per field. Uses the ``_UNSET`` sentinel
(not ``None``) for "no value yet", since several of these fields are
themselves ``Optional``-valued caches (e.g. ``rcp_privacy_cache: int |
None``) where a stored ``None`` is a legitimate cached value ("queried,
camera reported nothing") that must stay distinguishable from "never
queried" for `in`/`.get()` callers.

Deliberately NOT folded into Slice 2 (audited, not an oversight):
``_nvr_processes``/``_nvr_preroll_processes`` (live ``asyncio.subprocess.
Process`` handles, not simple cached data — same "needs its own dedicated
design" reasoning as ``_live_connections`` above), ``_nvr_preroll_tasks``
(``asyncio.Task`` handles), ``_nvr_recorder_locks``/
``_nvr_clip_assembly_locks`` (locks — Slice 4), and ``_nvr_drain_state``/
``_nvr_drain_failures`` — both LOOKED like per-cam_id caches from their
`dict[str, ...]` type hints and their presence in `_PURGE_CAM_DICT_ATTRS`,
but turned out on inspection of `recorder.py` to NOT be cam_id-keyed at
all: `_nvr_drain_state` is a single flat dict with fixed string keys
("target"/"pending"/"promoted"/"uploaded"/"failed"/"last_age_by_cam"/
"last_tick_ts") replaced wholesale every drain tick
(`recorder.py::sync_drain_tick`), and `_nvr_drain_failures` is keyed by
staging **file path**, not cam_id (`recorder.py:1774`,
`failures[full] = failures.get(full, 0) + 1`). Migrating either into a
per-cam `CameraSessionState` field would be actively wrong. Their
`_PURGE_CAM_DICT_ATTRS` membership was already a no-op in practice (a
cam_id never literally matches a staging file path or a fixed key like
"target"), so leaving them as plain dicts changes nothing.

Slice 3 of the ``docs/stream-perf-stability-refactor-plan.md`` "Session-
State-Facade — inkrementeller Migrationsplan" folds in the session-/
stream-state fields flagged there as higher-risk (actively read by
today's Phase 1/2/3 code): ``_live_connections`` and
``_user_intent_streams``. ``_sessions`` itself is NOT a migration target —
it already IS the base `dict[cam_id, CameraSessionState]` store every view
in this module is backed by. ``_live_opened_at``/``_stream_warming`` were
already folded before Slice 1 (see `LiveOpenedAtView`/`StreamWarmingView`
above) and needed no further work here.

``_live_connections`` (a `dict[str, dict[str, Any]]`, one ~15-key raw-JSON-
plus-derived-fields blob per cam_id) folds into a new
`live_connection: dict[str, Any] | _Unset` field via the EXISTING
`CacheFieldView[_T]` (Slice 2) — no new view class needed. Before relying
on this, `CacheFieldView`'s `.pop()` behavior (inherited from
`MutableMapping`, never previously exercised by Slice 2's callers) was
verified explicitly against a dedicated unit test covering: popping a
present key (returns the value, removes it), popping an absent key with a
default (returns the default, matches `dict.pop(k, default)`), and popping
an absent key with NO default (raises `KeyError`, matches `dict.pop(k)`).
All match plain-`dict` semantics exactly, confirming `MutableMapping.pop`'s
generic implementation (try `__getitem__` + `__delitem__`, catch
`KeyError`, fall back to `default`) is correct for this sentinel-based
storage. The two `.pop()` call sites the module docstring above originally
flagged (`camera.py`, `switch.py`) — since grown to more call sites across
`stream_lifecycle.py`/`live_connection.py` too — all use the
`.pop(cam_id, None)` two-arg form and keep working unchanged. The
nested-subscript-write pattern (`live = coordinator.live_connections.get
(cam_id); live["key"] = value`, used by `session_renewal.py`'s
credential-rotation path) also keeps working unchanged: `CacheFieldView.
__getitem__`/`.get()` return the SAME stored dict object, not a copy, so
in-place mutation persists into the backing `CameraSessionState.
live_connection` field exactly as it did into the old bare dict.

``_user_intent_streams`` (a `set[str]`, pure cam_id membership with no
associated value) folds into a new `user_intent_stream: bool` field via
the EXISTING `BoolFieldView` (Slice 1) — same reasoning as Slice 1's
"already logged/deferred" flags: membership in the old set is exactly
equivalent to a per-cam boolean flag, so no new view class is needed
either. All call sites (`switch.py`, `stream_lifecycle.py`) use only `in`/
`.add()`/`.discard()`, all already supported by `BoolFieldView`.

Both fields default to their view's normal "not set" sentinel
(`_UNSET`/`False` respectively) — matching `cam_id not in old_dict`/
`cam_id not in old_set` semantics exactly, so a freshly created
`CameraSessionState` (e.g. via `get_or_create_session` from an unrelated
field write) never spuriously reports an existing live connection or
user-intent flag for a camera that never had one.

No `race` between a `_live_connections` read and a concurrent
`_user_intent_streams` write is introduced by this migration: both fields
live on the SAME per-cam_id `CameraSessionState` instance now (previously
two entirely separate dicts), but neither this module nor any caller ever
held one field's read across an `await` while relying on the other field's
prior state — every call site reads-then-acts synchronously (no lock
contention was introduced or removed by folding both onto one dataclass
instance; attribute reads/writes on a single object are no more or less
atomic under asyncio's cooperative scheduling than two separate dict
accesses were).

Slice 4 of the ``docs/stream-perf-stability-refactor-plan.md`` "Session-
State-Facade — inkrementeller Migrationsplan" — the plan's final and
explicitly highest-risk slice ("Locks — höchstes Risiko, timing-kritisch")
— folds in the per-cam_id ``dict[str, asyncio.Lock]`` attributes. The task
that specified this slice named five (``_stream_locks``,
``_nvr_recorder_locks``, ``_snapshot_fetch_locks``,
``_go2rtc_reregister_locks``, ``_nvr_clip_assembly_locks``); a systematic
re-audit of every ``dict[str, asyncio.Lock]``-typed attribute in
``__init__.py`` (not just trusting that list) found a sixth that fits the
exact same criteria and had simply been missed: ``_fresh_snap_locks``
(per-camera lock coalescing concurrent ``async_fetch_fresh_event_snapshot``
calls after an FCM push — already routed through the shared
``lock_utils.get_or_create_lock`` helper; the ``lock_utils`` module
docstring's mention of it as an "inline setdefault variant" was stale, a
pre-existing doc/code drift unrelated to this migration). All six became
``asyncio.Lock | _Unset`` fields (``stream_lock``/``nvr_recorder_lock``/
``snapshot_fetch_lock``/``go2rtc_reregister_lock``/
``nvr_clip_assembly_lock``/``fresh_snap_lock``) via the EXISTING Slice 2
``CacheFieldView`` — no new view class needed, since a lock dict's external
contract (``.get(key)`` returning ``None`` for a missing key,
``store[key] = lock`` to insert) is already exactly what `CacheFieldView`
provides as a full `MutableMapping`.

Deliberately NOT migrated (excluded by the plan itself, audited again
here): ``_rcp_session_locks`` — keyed by `proxy_hash`, not `cam_id`; wrong
shape for a per-camera facade field, same reasoning as `_rcp_session_cache`
in the Slice 2 exclusion list. Also audited and left out of scope:
``guards.py::_get_cam_lock`` manages a structurally different per-cam lock
registry (``_audio_config_locks``, its only caller-supplied ``lock_attr``
today) that is never pre-declared in `BoschCameraCoordinator.__init__` at
all — lazily materialized via `getattr`/`setattr` on first use, and never a
member of `_PURGE_CAM_DICT_ATTRS` either (a pre-existing, unrelated gap,
not introduced or fixed by this slice). Slice 4's target is specifically
the coordinator's own pre-declared `__init__`-level lock dicts, so this
dynamic-attribute pattern was not folded in.

**Why identity is the whole risk here (unlike Slice 1-3's plain data
fields):** an `asyncio.Lock` is a stateful, identity-bearing object — two
different `Lock()` instances are NEVER interchangeable even both-unlocked.
The entire point of `_get_stream_lock(cam_id)` et al is that repeated calls
for the SAME `cam_id` return the SAME lock object, so that two coroutines
serializing on "the lock for this camera" are actually contending on one
shared object rather than each silently getting their own. `CacheFieldView`
was already verified (Slice 3) to return the SAME stored object reference
from `__getitem__`/`.get()` (not a copy) for mutable dict/list cache
values — that same "no copying" property is what makes it safe to reuse
here for `asyncio.Lock` values too: nothing in `CacheFieldView` ever
constructs a NEW value on read, it only ever returns exactly what was
`__setitem__`-stored (or raises/returns-default if nothing was). The
existing `lock_utils.get_or_create_lock(store, key)` helper — already used
unchanged by all five call sites, both before and after this migration —
supplies the actual "create on first access, return existing after" logic
via a synchronous (no `await` in between) check-then-insert on `store`;
`CacheFieldView` only had to keep behaving like a plain
`dict[str, asyncio.Lock]` for `.get()`/`__setitem__`, which it already did.
This was verified explicitly (not just reasoned about) in
`tests/test_session_state_facade_slice4.py` — including a real
two-coroutine `async with lock:` mutual-exclusion test, and a same-object
check performed WHILE the lock is held — before any production call site
was switched over.

A lock is never dropped while held: `_purge_cam_id` (the only code path
that ever removes a `CameraSessionState` — via `self._sessions.pop
(cam_id, None)`, which the Slice 4 lock fields ride along with, same as
every earlier slice) is documented and structurally guaranteed to run only
after `_cleanup_stale_devices` has confirmed a camera is gone from the
Bosch cloud account entirely — never mid-operation while one of that
camera's locks could be `locked()` by an in-flight coroutine. This
guarantee predates Slice 4 (the old bare-dict `_stream_locks.pop(cam_id,
None)` etc. had the exact same "never mid-operation" precondition) and is
unchanged by moving the lock onto the shared `CameraSessionState` object —
popping the WHOLE session (all its fields, locks included) together is no
more or less safe than popping just the lock dict entry used to be, given
that precondition holds.
"""

import asyncio
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from typing import Any, TypeVar, cast, overload, override

_T = TypeVar("_T")


class _Unset:
    """Sentinel type for an unpopulated `CameraSessionState` cache field.

    A dedicated type (not `None`) because several Slice 2 fields are
    themselves `Optional`-valued caches (e.g. `rcp_privacy_cache: int |
    None`) — a stored `None` there is a legitimate cached value that must
    stay distinguishable from "never queried".
    """

    __slots__ = ()

    @override
    def __repr__(self) -> str:
        return "<unset>"


_UNSET = _Unset()


@dataclass
class CameraSessionState:
    """Per-camera live-session bookkeeping.

    ``idle_since``/``opened_at`` use ``None``, ``warming_started`` uses
    ``float('-inf')``, as their "not currently set" sentinel — matching the
    exact semantics of the dict/set lookups they replace (SENTINEL_RULE:
    never ``0.0`` for "never done", since CI/production hosts boot with a
    nonzero monotonic clock already).

    Slice 1 fields below all use ``None`` as their "not set" sentinel for
    the float write-lock timestamps (matching ``idle_since``/``opened_at``
    above, and preserving the exact `dict.get(cam_id, default)` semantics
    of the dicts they replace — callers supply their own default, most
    commonly ``float('-inf')`` per SENTINEL_RULE) and ``False`` for the
    bool "already logged/deferred" flags (matching the `not in a_set`
    semantics of the sets they replace).
    """

    generation: int = 0
    idle_since: float | None = None
    warming_started: float = float("-inf")
    warming: bool = False
    opened_at: float | None = None
    # ── Slice 1: diagnostic/write-lock timestamps ──────────────────────
    offline_seen_at: float | None = None
    light_set_at: float | None = None
    notif_set_at: float | None = None
    privacy_set_at: float | None = None
    privacy_sound_set_at: float | None = None
    timestamp_set_at: float | None = None
    ledlights_set_at: float | None = None
    arming_set_at: float | None = None
    intrusion_config_set_at: float | None = None
    audio_detection_set_at: float | None = None
    motion_set_at: float | None = None
    alarm_settings_set_at: float | None = None
    lighting_options_set_at: float | None = None
    firmware_set_at: float | None = None
    # ── Slice 1: "already logged/deferred this cycle" flags ────────────
    notif_disabled_logged: bool = False
    fw_update_alerted: bool = False
    slow_tier_deferred: bool = False
    # ── Slice 2: per-cam caches without cross-camera access ─────────────
    # All default to the `_UNSET` sentinel (see `_Unset` above) — matches
    # the `cam_id not in old_dict` semantics of the dicts they replace.
    rcp_state_cache: dict[str, Any] | _Unset = _UNSET
    shc_state_cache: dict[str, Any] | _Unset = _UNSET
    pan_cache: int | None | _Unset = _UNSET
    rcp_dimmer_cache: int | None | _Unset = _UNSET
    rcp_privacy_cache: int | None | _Unset = _UNSET
    rcp_clock_offset_cache: float | None | _Unset = _UNSET
    rcp_lan_ip_cache: str | None | _Unset = _UNSET
    rcp_product_name_cache: str | None | _Unset = _UNSET
    rcp_bitrate_cache: list[int] | _Unset = _UNSET
    rcp_alarm_catalog_cache: list[dict[str, Any]] | _Unset = _UNSET
    rcp_motion_zones_cache: list[dict[str, Any]] | _Unset = _UNSET
    rcp_motion_coords_cache: list[dict[str, Any]] | _Unset = _UNSET
    rcp_tls_cert_cache: dict[str, Any] | _Unset = _UNSET
    rcp_network_services_cache: list[str] | _Unset = _UNSET
    rcp_iva_catalog_cache: list[dict[str, Any]] | _Unset = _UNSET
    rcp_onvif_scopes_cache: dict[str, Any] | _Unset = _UNSET
    rcp_version_cache: str | None | _Unset = _UNSET
    nvr_mode_preference: str | _Unset = _UNSET
    local_creds_cache: dict[str, Any] | _Unset = _UNSET
    audio_cache: dict[str, Any] | _Unset = _UNSET
    nvr_user_intent: bool | _Unset = _UNSET
    nvr_error_state: str | _Unset = _UNSET
    nvr_recent_crash: float | _Unset = _UNSET
    nvr_auth_retry_count: int | _Unset = _UNSET
    nvr_event_clip_enabled: bool | _Unset = _UNSET
    nvr_preroll_last_crash: float | _Unset = _UNSET
    nvr_preroll_segment_counts: int | _Unset = _UNSET
    # ── Slice 3: session/stream state ───────────────────────────────────
    live_connection: dict[str, Any] | _Unset = _UNSET
    user_intent_stream: bool = False
    # ── Slice 4: per-camera locks ────────────────────────────────────────
    # All default to `_UNSET` (see `_Unset` above) — matches the
    # `cam_id not in old_dict` semantics of the `dict[str, asyncio.Lock]`
    # attributes they replace, so `lock_utils.get_or_create_lock`'s
    # `store.get(key)` check keeps returning `None` (not a spuriously
    # pre-created Lock) for a camera that never needed this lock yet.
    stream_lock: asyncio.Lock | _Unset = _UNSET
    nvr_recorder_lock: asyncio.Lock | _Unset = _UNSET
    snapshot_fetch_lock: asyncio.Lock | _Unset = _UNSET
    go2rtc_reregister_lock: asyncio.Lock | _Unset = _UNSET
    nvr_clip_assembly_lock: asyncio.Lock | _Unset = _UNSET
    fresh_snap_lock: asyncio.Lock | _Unset = _UNSET


def get_or_create_session(
    store: dict[str, CameraSessionState], cam_id: str
) -> CameraSessionState:
    """Return the `CameraSessionState` for `cam_id` in `store`, creating it if absent.

    Safe under asyncio: check-then-insert has no `await` between the two
    steps, so concurrent coroutines cannot interleave here (same idiom as
    `lock_utils.get_or_create_lock`).
    """
    session = store.get(cam_id)
    if session is None:
        session = CameraSessionState()
        store[cam_id] = session
    return session


class StreamWarmingView:
    """Set-like facade over `CameraSessionState.warming`.

    Preserves the `_stream_warming: set[str]` contract external callers
    (`camera.py`: `in`/`not in`) rely on, without them needing to change.
    """

    def __init__(self, sessions: dict[str, CameraSessionState]) -> None:
        self._sessions = sessions

    def __contains__(self, cam_id: str) -> bool:
        session = self._sessions.get(cam_id)
        return session is not None and session.warming

    def add(self, cam_id: str) -> None:
        get_or_create_session(self._sessions, cam_id).warming = True

    def discard(self, cam_id: str) -> None:
        session = self._sessions.get(cam_id)
        if session is not None:
            session.warming = False

    def __len__(self) -> int:
        return sum(1 for session in self._sessions.values() if session.warming)


class LiveOpenedAtView:
    """Dict-like facade over `CameraSessionState.opened_at`.

    Preserves the `_live_opened_at: dict[str, float]` contract external
    callers (`camera.py`: `.get()`/`.pop()`) rely on, without them needing
    to change.
    """

    def __init__(self, sessions: dict[str, CameraSessionState]) -> None:
        self._sessions = sessions

    @overload
    def get(self, cam_id: str) -> float | None: ...
    @overload
    def get(self, cam_id: str, default: float) -> float: ...
    @overload
    def get(self, cam_id: str, default: float | None) -> float | None: ...
    def get(self, cam_id: str, default: float | None = None) -> float | None:
        session = self._sessions.get(cam_id)
        if session is None or session.opened_at is None:
            return default
        return session.opened_at

    def pop(self, cam_id: str, default: float | None = None) -> float | None:
        session = self._sessions.get(cam_id)
        if session is None or session.opened_at is None:
            return default
        val = session.opened_at
        session.opened_at = None
        return val

    def __setitem__(self, cam_id: str, value: float) -> None:
        get_or_create_session(self._sessions, cam_id).opened_at = value

    def __len__(self) -> int:
        return sum(
            1 for session in self._sessions.values() if session.opened_at is not None
        )


class FloatFieldView:
    """Dict-like facade over a named ``float | None`` field of `CameraSessionState`.

    Generalizes `LiveOpenedAtView` for reuse across the Slice 1 write-lock
    timestamp fields (``offline_seen_at``/every ``*_set_at`` — see the
    module docstring) — one instance per field, parameterized by
    `field_name`, instead of one hand-rolled class per field. Preserves the
    exact `dict[str, float]` contract (`.get()`/`[cam_id] = ...`/`.pop()`/
    `in`) external callers already rely on.
    """

    def __init__(
        self, sessions: dict[str, CameraSessionState], field_name: str
    ) -> None:
        self._sessions = sessions
        self._field_name = field_name

    @overload
    def get(self, cam_id: str) -> float | None: ...
    @overload
    def get(self, cam_id: str, default: float) -> float: ...
    @overload
    def get(self, cam_id: str, default: float | None) -> float | None: ...
    def get(self, cam_id: str, default: float | None = None) -> float | None:
        session = self._sessions.get(cam_id)
        if session is None:
            return default
        value: float | None = getattr(session, self._field_name)
        return default if value is None else value

    def __setitem__(self, cam_id: str, value: float) -> None:
        setattr(get_or_create_session(self._sessions, cam_id), self._field_name, value)

    def __contains__(self, cam_id: str) -> bool:
        session = self._sessions.get(cam_id)
        return session is not None and getattr(session, self._field_name) is not None

    def __getitem__(self, cam_id: str) -> float:
        """Raise `KeyError` if unset — matches `dict[str, float][cam_id]` semantics
        for the `cam_id in view and view[cam_id]` call-site pattern.
        """
        session = self._sessions.get(cam_id)
        value: float | None = (
            None if session is None else getattr(session, self._field_name)
        )
        if value is None:
            raise KeyError(cam_id)
        return value

    def pop(self, cam_id: str, default: float | None = None) -> float | None:
        session = self._sessions.get(cam_id)
        if session is None:
            return default
        value: float | None = getattr(session, self._field_name)
        if value is None:
            return default
        setattr(session, self._field_name, None)
        return value

    def __len__(self) -> int:
        return sum(
            1
            for session in self._sessions.values()
            if getattr(session, self._field_name) is not None
        )


class BoolFieldView:
    """Set-like facade over a named `bool` field of `CameraSessionState`.

    Generalizes `StreamWarmingView` for reuse across the Slice 1
    "already logged/deferred this cycle" flags (``notif_disabled_logged``,
    ``fw_update_alerted``, ``slow_tier_deferred`` — see the module
    docstring) — one instance per field, parameterized by `field_name`.
    Preserves the exact `set[str]` contract (`in`/`.add()`/`.discard()`)
    external callers already rely on.
    """

    def __init__(
        self, sessions: dict[str, CameraSessionState], field_name: str
    ) -> None:
        self._sessions = sessions
        self._field_name = field_name

    def __contains__(self, cam_id: str) -> bool:
        session = self._sessions.get(cam_id)
        return session is not None and bool(getattr(session, self._field_name))

    def add(self, cam_id: str) -> None:
        setattr(get_or_create_session(self._sessions, cam_id), self._field_name, True)

    def discard(self, cam_id: str) -> None:
        session = self._sessions.get(cam_id)
        if session is not None:
            setattr(session, self._field_name, False)

    def __len__(self) -> int:
        return sum(
            1
            for session in self._sessions.values()
            if getattr(session, self._field_name)
        )


class CacheFieldView(MutableMapping[str, _T]):
    """`MutableMapping[str, _T]` facade over a named per-camera cache field
    of `CameraSessionState` (Session-State-Facade Slice 2 — see the module
    docstring).

    Generalizes `FloatFieldView`/`BoolFieldView` (Slice 1) for Slice 2's
    heterogeneous cache value types (dict/list/int/str/float/bool, several
    of them themselves `Optional`) — one instance per field, parameterized
    by `field_name`, built on `collections.abc.MutableMapping` rather than
    hand-writing every dict method: only `__getitem__`/`__setitem__`/
    `__delitem__`/`__iter__`/`__len__` are implemented below, and the mixin
    supplies `.get()`/`.pop()`/`.setdefault()`/`.update()`/`.clear()`/
    `.items()`/`.values()`/`.keys()`/`in`/`==`/`bool()` on top — including
    the two whole-dict-iteration call sites this slice's caches have
    (`_rcp_lan_ip_cache` in `__init__.py`'s outage-ping loop and
    `tick_housekeeping.py`'s persisted-snapshot comprehension;
    `_local_creds_cache` in the same `tick_housekeeping.py` snapshot path)
    and the nested-subscript-write pattern several `_shc_state_cache`
    writers use (`cache[cam_id]["key"] = value`) — `__getitem__` returns
    the SAME stored object reference (not a copy), so in-place mutation of
    a returned dict/list persists correctly.

    Uses the `_UNSET` sentinel (not `None`) for "no cached value for this
    cam_id yet" — see `_Unset` above.
    """

    def __init__(
        self, sessions: dict[str, CameraSessionState], field_name: str
    ) -> None:
        self._sessions = sessions
        self._field_name = field_name

    @override
    def __getitem__(self, cam_id: str) -> _T:
        session = self._sessions.get(cam_id)
        value: object = (
            _UNSET if session is None else getattr(session, self._field_name)
        )
        if value is _UNSET:
            raise KeyError(cam_id)
        return cast("_T", value)

    @override
    def __setitem__(self, cam_id: str, value: _T) -> None:
        setattr(get_or_create_session(self._sessions, cam_id), self._field_name, value)

    @override
    def __delitem__(self, cam_id: str) -> None:
        session = self._sessions.get(cam_id)
        value: object = (
            _UNSET if session is None else getattr(session, self._field_name)
        )
        if value is _UNSET:
            raise KeyError(cam_id)
        setattr(session, self._field_name, _UNSET)

    @override
    def __iter__(self) -> Iterator[str]:
        # Materialized eagerly (not a lazy generator) so that another
        # field's `get_or_create_session()` call elsewhere growing the
        # shared `_sessions` dict mid-loop cannot raise "dictionary
        # changed size during iteration" on a caller iterating THIS view
        # (`for cid in coordinator.rcp_lan_ip_cache:` etc.) — the
        # original dedicated per-field dict this replaces never had that
        # cross-field growth risk, so preserving eager materialization
        # keeps the exact same failure mode (none).
        return iter(
            [
                cam_id
                for cam_id, session in self._sessions.items()
                if getattr(session, self._field_name) is not _UNSET
            ]
        )

    @override
    def __len__(self) -> int:
        return sum(
            1
            for session in self._sessions.values()
            if getattr(session, self._field_name) is not _UNSET
        )

    @override
    def __repr__(self) -> str:
        return f"CacheFieldView({dict(self)!r})"
