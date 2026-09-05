"""API parser for JSON APIs."""

from collections.abc import Hashable, Mapping
from datetime import UTC, datetime
from logging import getLogger
from typing import Any, TypedDict

_LOGGER = getLogger(__name__)


MILLIS_TIMESTAMP_THRESHOLD: int = 100_000_000_000
"""Values above this are millisecond-, not second-based Unix timestamps."""

# Distinct from None, which can be a legitimate API value.
_MISSING = object()

_BOOL_TRUE_VALUES = {"on", "yes", "up", "true", "1"}
_BOOL_FALSE_VALUES = {"off", "no", "down", "false", "0"}

_SUPPORTED_VALS_PROC_ACTIONS = {"combine"}


# ---------------------------
#   ApiValueSpec
# ---------------------------
class ApiValueSpec(TypedDict, total=False):
    """Specification for values parsed from the API."""

    name: str
    type: str
    source: str
    default: Any
    default_val: str
    reverse: bool
    convert: str


# ---------------------------
#   utc_from_timestamp
# ---------------------------
def utc_from_timestamp(timestamp: float) -> datetime:
    """Return a UTC time from a timestamp."""
    return datetime.fromtimestamp(timestamp, tz=UTC)


# ---------------------------
#   human_date_to_utc
# ---------------------------
def human_date_to_utc(date_str: Any) -> datetime | None:
    """Parse a TrueNAS certificate 'until' date, e.g. "Fri Mar 26 00:59:59 2100"."""
    if not isinstance(date_str, str):
        _LOGGER.debug("Expected certificate date string, got: %r", date_str)
        return None
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %Y").replace(tzinfo=UTC)
    except (ValueError, AttributeError):  # fmt: skip
        _LOGGER.debug("Failed to parse certificate date: %s", date_str)
        return None


# ---------------------------
#   _resolve_source
# ---------------------------
def _resolve_source(entry: dict[str, Any] | None, param: str) -> Any:
    """Resolve param (supporting '/'-nested paths) or return _MISSING."""
    if "/" not in param:
        return entry[param] if isinstance(entry, dict) and param in entry else _MISSING

    current: Any = entry
    for tmp_param in param.split("/"):
        if isinstance(current, dict) and tmp_param in current:
            current = current[tmp_param]
        else:
            return _MISSING
    return current


# ---------------------------
#   from_entry
# ---------------------------
def from_entry(
    entry: dict[str, Any] | None,
    param: str,
    default: Any = "",
    max_len: int | None = 255,
    round_digits: int | None = None,
) -> Any:
    """Validate and return value from an API dict."""
    ret = _resolve_source(entry, param)
    if ret is _MISSING:
        return default

    if isinstance(ret, float) and round_digits is not None:
        ret = round(ret, round_digits)

    if isinstance(ret, str) and max_len is not None and len(ret) > max_len:
        return ret[:max_len]
    return ret


# ---------------------------
#   _coerce_bool
# ---------------------------
def _coerce_bool(value: Any, default: bool) -> bool:
    """Coerce a resolved value into a bool, falling back to default."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _BOOL_TRUE_VALUES:
            return True
        if normalized in _BOOL_FALSE_VALUES:
            return False

    return value if isinstance(value, bool) else default


# ---------------------------
#   from_entry_bool
# ---------------------------
def from_entry_bool(
    entry: dict[str, Any] | None,
    param: str,
    default: bool = False,
    reverse: bool = False,
) -> bool:
    """Validate and return a bool value from an API dict."""
    ret = _resolve_source(entry, param)
    if ret is _MISSING:
        return default

    ret = _coerce_bool(ret, default)
    return not ret if reverse else ret


# ---------------------------
#   _str_default / _bool_default / _spec_default
# ---------------------------
def _str_default(val: Mapping[str, Any]) -> Any:
    """Return the default for a string-typed value spec."""
    if "default_val" in val and val["default_val"] in val:
        return val[val["default_val"]]
    return val.get("default", "")


def _bool_default(val: Mapping[str, Any]) -> bool:
    """Return the default for a bool-typed value spec."""
    default = val.get("default", False)
    return not default if val.get("reverse", False) else default


def _spec_default(val: Mapping[str, Any]) -> Any:
    """Return the configured default value for a value spec."""
    if val.get("type", "str") == "bool":
        return _bool_default(val)
    return _str_default(val)


# ---------------------------
#   parse_api
# ---------------------------
def parse_api(
    data: dict[str, Any] | None = None,
    source: dict[str, Any] | list[Any] | str | None = None,
    key: str | None = None,
    key_secondary: str | None = None,
    key_search: str | None = None,
    vals: list[ApiValueSpec] | None = None,
    val_proc: list[list[dict[str, Any]]] | None = None,
    ensure_vals: list[ApiValueSpec] | None = None,
    only: list[dict[str, Any]] | None = None,
    skip: list[dict[str, Any]] | None = None,
    prune: bool = True,
) -> dict[str, Any]:
    """Get data from API.

    For keyed/key_search'd data, a uid present in ``data`` from a previous
    call but absent from this (non-empty) ``source`` is dropped: it means
    the underlying object (disk, pool, task, app, interface, ...) no longer
    exists, so keeping it would leave a stale entity behind indefinitely.
    See ``_empty_source_result`` for the None-source (query failed) and
    empty-list-source (nothing left at all) cases.

    ``prune=False`` opts out of that dropping for callers that intentionally
    pass a partial ``source`` covering only a subset of ``data`` (e.g. adding
    a single extra record to an already-populated map) -- otherwise every
    uid outside that subset would be misread as removed and deleted.
    """
    if data is None:
        data = {}
    if isinstance(source, dict):
        source = [source]
    elif isinstance(source, str):
        # A bare string is a malformed payload; treat as no source.
        source = None

    if not source:
        return _empty_source_result(data, key, key_search, vals, source is None)

    keymap = generate_keymap(data, key_search)
    seen_uids: set[str] = set()
    for entry in source:
        if not isinstance(entry, dict):
            # Skip non-dict entries so lookups below don't raise.
            continue
        if _should_skip_entry(entry, only, skip):
            continue

        uid, matched = _resolve_entry_uid(
            data, entry, key, key_secondary, key_search, keymap
        )
        if not matched:
            continue
        if uid is not None:
            seen_uids.add(uid)

        data = _apply_entry(data, entry, uid, vals, ensure_vals, val_proc)

    if prune:
        _prune_stale_uids(data, key, key_search, seen_uids)

    return data


# ---------------------------
#   _prune_stale_uids
# ---------------------------
def _prune_stale_uids(
    data: dict[str, Any], key: str | None, key_search: str | None, seen_uids: set[str]
) -> None:
    """Drop keyed/key_search'd entries no longer present in the current source."""
    if not (key or key_search):
        return
    for stale_uid in set(data) - seen_uids:
        del data[stale_uid]


# ---------------------------
#   _empty_source_result
# ---------------------------
def _empty_source_result(
    data: dict[str, Any],
    key: str | None,
    key_search: str | None,
    vals: list[ApiValueSpec] | None,
    source_was_none: bool,
) -> dict[str, Any]:
    """Return data for an empty/missing source.

    Keyless (single-object) data always falls back to its declared defaults
    -- ``fill_defaults`` only fills keys not already present, so this can
    never overwrite good values, whether the source failed outright or
    genuinely came back empty. Keyed data is different: a ``None`` source
    means the query itself failed or returned malformed data, so the
    previous snapshot is kept untouched rather than wiping out good state on
    a transient error; an explicit empty list is a genuine "nothing left"
    result (e.g. the last disk/pool/app was removed), so it's pruned.
    """
    if not key and not key_search:
        return fill_defaults(data, vals)
    return data if source_was_none else {}


# ---------------------------
#   _should_skip_entry
# ---------------------------
def _should_skip_entry(
    entry: dict[str, Any],
    only: list[dict[str, Any]] | None,
    skip: list[dict[str, Any]] | None,
) -> bool:
    """Return True if an entry should be excluded by only/skip filters."""
    if only and not matches_only(entry, only):
        return True
    return bool(skip and can_skip(entry, skip))


# ---------------------------
#   _resolve_entry_uid
# ---------------------------
def _resolve_entry_uid(
    data: dict[str, Any],
    entry: dict[str, Any],
    key: str | None,
    key_secondary: str | None,
    key_search: str | None,
    keymap: dict[Hashable, str] | None,
) -> tuple[str | None, bool]:
    """Resolve the uid for an entry; matched=False means the entry should be skipped."""
    if not (key or key_search):
        return None, True

    uid = get_uid(entry, key, key_secondary, key_search, keymap)
    if uid is None:
        return None, False

    if uid not in data:
        data[uid] = {}
    return uid, True


# ---------------------------
#   _apply_entry
# ---------------------------
def _apply_entry(
    data: dict[str, Any],
    entry: dict[str, Any],
    uid: str | None,
    vals: list[ApiValueSpec] | None,
    ensure_vals: list[ApiValueSpec] | None,
    val_proc: list[list[dict[str, Any]]] | None,
) -> dict[str, Any]:
    """Apply the vals/ensure_vals/val_proc processors to a single entry."""
    if vals:
        data = fill_vals(data, entry, uid, vals)
    if ensure_vals:
        data = fill_ensure_vals(data, uid, ensure_vals)
    if val_proc:
        data = fill_vals_proc(data, uid, val_proc)
    return data


# ---------------------------
#   get_uid
# ---------------------------
def get_uid(
    entry: Any,
    key: str | None,
    key_secondary: str | None,
    key_search: str | None,
    keymap: dict[Hashable, str] | None,
) -> str | None:
    """Get UID for data list."""
    if not isinstance(entry, dict):
        return None

    uid: str | None = None
    if not key_search:
        if key is not None and key in entry:
            uid = entry[key]
        elif key_secondary is not None:
            uid = entry.get(key_secondary)
    elif keymap and key_search is not None and key_search in entry:
        uid = keymap.get(entry[key_search])

    return uid


# ---------------------------
#   generate_keymap
# ---------------------------
def generate_keymap(
    data: dict[str, Any], key_search: str | None
) -> dict[Hashable, str] | None:
    """Generate keymap, skipping entries that aren't dicts or lack key_search."""
    if not key_search:
        return None
    return {
        entry[key_search]: uid
        for uid in data
        if isinstance(entry := data[uid], dict)
        and key_search in entry
        and isinstance(entry[key_search], Hashable)
    }


# ---------------------------
#   matches_only
# ---------------------------
def matches_only(entry: dict[str, Any], only: list[dict[str, Any]]) -> bool:
    """Return True if all variables are matched."""
    return all(entry.get(val["key"]) == val["value"] for val in only)


# ---------------------------
#   can_skip
# ---------------------------
def can_skip(entry: dict[str, Any], skip: list[dict[str, Any]]) -> bool:
    """Return True if at least one variable matches."""
    ret = False
    for val in skip:
        if val["name"] in entry and entry[val["name"]] == val["value"]:
            ret = True
            break

        if val["value"] == "" and val["name"] not in entry:
            ret = True
            break

    return ret


# ---------------------------
#   fill_defaults
# ---------------------------
def fill_defaults(
    data: dict[str, Any] | None, vals: list[ApiValueSpec] | None
) -> dict[str, Any]:
    """Fill defaults if source is not present."""
    if data is None:
        data = {}
    if not vals:
        return data

    for val in vals:
        name = val["name"]
        if name not in data:
            data[name] = _spec_default(val)

    return data


# ---------------------------
#   _convert_timestamp
# ---------------------------
def _convert_timestamp(target: dict[str, Any], name: str) -> None:
    """Convert an int timestamp at target[name] to a UTC datetime, or None.

    Non-timestamp values become None instead of a bad state (e.g. TrueNAS's
    scan.end_time=null during a scrub becomes 0 via the spec's default).
    """
    value = target.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        target[name] = None
        return

    if value > MILLIS_TIMESTAMP_THRESHOLD:
        value = value / 1000
    target[name] = utc_from_timestamp(value)


# ---------------------------
#   _convert_human_date
# ---------------------------
def _convert_human_date(target: dict[str, Any], name: str) -> None:
    """Convert human-readable date string to UTC datetime or None if unparsable."""
    target[name] = human_date_to_utc(target.get(name))


# ---------------------------
#   _set_val
# ---------------------------
def _set_val(
    target: dict[str, Any], entry: dict[str, Any], val: Mapping[str, Any]
) -> None:
    """Resolve a single value spec into target."""
    name = val["name"]
    source = val.get("source", name)

    if val.get("type", "str") == "bool":
        target[name] = from_entry_bool(
            entry, source, default=_bool_default(val), reverse=val.get("reverse", False)
        )
    else:
        target[name] = from_entry(entry, source, default=_str_default(val))

    if val.get("convert") == "utc_from_timestamp":
        _convert_timestamp(target, name)
    elif val.get("convert") == "human_date_to_utc":
        _convert_human_date(target, name)


# ---------------------------
#   fill_vals
# ---------------------------
def fill_vals(
    data: dict[str, Any],
    entry: dict[str, Any],
    uid: str | None,
    vals: list[ApiValueSpec],
) -> dict[str, Any]:
    """Fill all data."""
    target: dict[str, Any] = data[uid] if uid is not None else data
    for val in vals:
        _set_val(target, entry, val)

    return data


# ---------------------------
#   fill_ensure_vals
# ---------------------------
def fill_ensure_vals(
    data: dict[str, Any], uid: str | None, ensure_vals: list[ApiValueSpec]
) -> dict[str, Any]:
    """Add required keys which are not available in data."""
    if uid is not None and uid not in data:
        data[uid] = {}

    target: dict[str, Any] = data[uid] if uid is not None else data
    for val in ensure_vals:
        name = val["name"]
        if name not in target:
            target[name] = val.get("default", "")

    return data


# ---------------------------
#   _validate_action / _combine_value / _process_val_sub
# ---------------------------
def _validate_action(action: str, name: str | None) -> str:
    """Validate a vals_proc action, raising for unsupported actions."""
    if action not in _SUPPORTED_VALS_PROC_ACTIONS:
        raise ValueError(
            f"Unsupported action '{action}' in vals_proc for name '{name}'"
        )
    return action


def _combine_value(source: dict[str, Any], val: dict[str, Any], value: Any) -> Any:
    """Append a key's value and/or literal text to the accumulated value."""
    if "key" in val:
        tmp = source.get(val["key"], "unknown")
        value = f"{value}{tmp}" if value else tmp

    if "text" in val:
        tmp = val["text"]
        value = f"{value}{tmp}" if value else tmp

    return value


def _process_val_sub(
    source: dict[str, Any], val_sub: list[dict[str, Any]]
) -> tuple[str | None, Any]:
    """Resolve a single val_proc spec into a (name, value) pair."""
    name: str | None = None
    action: str | None = None
    value: Any = None

    for val in val_sub:
        if "name" in val:
            name = val["name"]
            continue

        if "action" in val:
            action = _validate_action(val["action"], name)
            continue

        if name is None or action is None:
            break

        if action == "combine":
            value = _combine_value(source, val, value)

    return name, value


# ---------------------------
#   fill_vals_proc
# ---------------------------
def fill_vals_proc(
    data: dict[str, Any], uid: str | None, vals_proc: list[list[dict[str, Any]]]
) -> dict[str, Any]:
    """Add custom keys."""
    target: dict[str, Any] = data[uid] if uid is not None else data

    for val_sub in vals_proc:
        name, value = _process_val_sub(target, val_sub)
        if name and value is not None:
            target[name] = value

    return data
