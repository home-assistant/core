"""Text form of the time-of-use plan: formatting, parsing and write-back.

The whole `time_cfg` is packed into one text entity on a single line:

    09:00-09:10|discharge|200|1234567|1;10:00-10:10|self|-|1234567|1

Two hard constraints shape that format:
- A text entity is a single-line ``<input>``, so a newline cannot be typed and
  rules are separated by ``;`` instead.
- The entity state is capped at 255 characters, which also caps the rule count
  (see const.LAKE6_TOU_TEXT_MAX_RULES).

This module only converts formats with pure functions and does not depend on HA
entities. Validation failures always raise ValueError, which the text platform
translates into a ServiceValidationError.
"""

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .client import Lake6TouRule
from .const import (
    LAKE6_TOU_PERMIT_KEYS,
    LAKE6_TOU_POWER_MAX,
    LAKE6_TOU_POWER_MIN,
    LAKE6_TOU_STATE_TO_TEXT_FUNCTION,
    LAKE6_TOU_TEXT_FIELD_SEPARATOR,
    LAKE6_TOU_TEXT_FUNCTION_SELF,
    LAKE6_TOU_TEXT_FUNCTION_TO_CODE,
    LAKE6_TOU_TEXT_FUNCTION_TO_PERMIT,
    LAKE6_TOU_TEXT_MAX_RULES,
    LAKE6_TOU_TEXT_POWER_PLACEHOLDER,
    LAKE6_TOU_TEXT_RULE_SEPARATOR,
    LAKE6_TOU_TEXT_WEEKDAY_LIST_SEPARATOR,
    LAKE6_TOU_TEXT_WEEKDAY_RANGE_SEPARATOR,
)

if TYPE_CHECKING:
    from ..coordinator import Lake6Coordinator

_FALSE_FLAGS = frozenset({"0", "off", "false", "no"})
_TRUE_FLAGS = frozenset({"1", "on", "true", "yes"})


@dataclass(frozen=True, kw_only=True)
class Lake6TouPlanRow:
    """One line of text, i.e. one rule on the device.

    `function` holds the text abbreviation (`charge` / `discharge` / `self`) and
    not the device code: it is also the formatting output, which avoids
    converting between two representations.
    """

    enabled: bool
    weekdays: list[int]
    start: str
    end: str
    function: str
    # None for self-consumption, which carries no power.
    power: int | None
    # Set when a self-consumption row carried a power value that was dropped, so
    # the text platform can warn the user.
    power_ignored: bool = False


def format_weekdays(weekdays: list[int]) -> str:
    """Compress the weekday list: `12345` means Monday to Friday."""
    return "".join(str(day) for day in sorted(set(weekdays)))


def parse_weekdays(value: str) -> list[int]:
    """Parse the weekday field into a sorted, de-duplicated list.

    Accepts the compact form ``12345``, ranges like ``1-5`` and lists like
    ``1,3,5``, and the three can be mixed.

    Raises:
        ValueError: A fragment is not a single digit from 1 to 7, or the ends of
            a range are reversed.
    """
    days: set[int] = set()
    for chunk in value.replace(" ", "").split(LAKE6_TOU_TEXT_WEEKDAY_LIST_SEPARATOR):
        if not chunk:
            continue
        head, separator, tail = chunk.partition(LAKE6_TOU_TEXT_WEEKDAY_RANGE_SEPARATOR)
        if separator:
            first = _weekday_number(head)
            last = _weekday_number(tail)
            if first > last:
                raise ValueError(f"weekday range out of order {chunk!r}")
            days.update(range(first, last + 1))
        else:
            days.update(_weekday_number(char) for char in chunk)
    return sorted(days)


def render_plan(rules: list[Lake6TouRule]) -> str | None:
    """Render the rules the device reports into text.

    Returns None as soon as one rule cannot be expressed completely (missing
    time, unknown function code, power out of range). A plan that silently drops
    a row would delete that row from the device once the user submits it back
    unchanged.
    """
    rows = [_format_rule(rule) for rule in rules]
    if any(row is None for row in rows):
        return None
    return LAKE6_TOU_TEXT_RULE_SEPARATOR.join(row for row in rows if row is not None)


def parse_plan(value: str) -> list[Lake6TouPlanRow]:
    """Parse the text into a list of rules.

    Raises:
        ValueError: The format is wrong, a rule does not have five fields, or
            there are more rules than the text form allows.
    """
    chunks = [chunk.strip() for chunk in value.split(LAKE6_TOU_TEXT_RULE_SEPARATOR)]
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        raise ValueError("plan is empty")
    if len(chunks) > LAKE6_TOU_TEXT_MAX_RULES:
        raise ValueError(f"at most {LAKE6_TOU_TEXT_MAX_RULES} rules")
    return [_parse_row(chunk) for chunk in chunks]


def build_payload(
    raw: list[dict[str, Any]],
    rows: list[Lake6TouPlanRow],
) -> list[dict[str, Any]]:
    """Merge the parsed rules into the raw `time_cfg`.

    Each row reuses its original dict so keys this integration does not parse
    survive. `GC` / `GD` are the exception: they belong to the current function
    and are rebuilt on every write, see `_apply_row`. The device replaces
    `time_cfg` as a whole, so the full array is sent every time.
    """
    payload: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        entry = copy.deepcopy(raw[index]) if index < len(raw) else {}
        _apply_row(entry, row)
        payload.append(entry)
    return payload


async def async_write_tou_plan(
    coordinator: Lake6Coordinator,
    rows: list[Lake6TouPlanRow],
) -> None:
    """Write the complete time-of-use plan."""
    payload = build_payload(coordinator.data.modes.time_cfg, rows)
    await coordinator.async_set_modes(time_cfg=payload)


def _weekday_number(text: str) -> int:
    """Convert one weekday character to an integer from 1 to 7.

    Raises:
        ValueError: The input is not a single digit from 1 to 7.
    """
    if len(text) != 1 or not text.isdigit():
        raise ValueError(f"invalid weekday {text!r}")
    day = int(text)
    if not 1 <= day <= 7:
        raise ValueError(f"invalid weekday {text!r}")
    return day


def _parse_hhmm(value: str) -> str:
    """Validate and normalize one `HH:MM` time.

    Raises:
        ValueError: The value is not `HH:MM`, or the hour/minute is out of
            range.
    """
    hours_text, separator, minutes_text = value.strip().partition(":")
    if not separator or not hours_text.isdigit() or not minutes_text.isdigit():
        raise ValueError(f"invalid time {value!r}")
    hours, minutes = int(hours_text), int(minutes_text)
    if hours > 23 or minutes > 59:
        raise ValueError(f"invalid time {value!r}")
    return f"{hours:02d}:{minutes:02d}"


def _parse_time_range(value: str) -> tuple[str, str]:
    """Split `HH:MM-HH:MM` into a start and an end time.

    The protocol does not allow crossing midnight, so an end at or before the
    start is invalid.

    Raises:
        ValueError: The separator is missing, a time is invalid, or the span is
            zero or negative.
    """
    start_text, separator, end_text = value.partition("-")
    if not separator:
        raise ValueError(f"invalid time range {value!r}")
    start = _parse_hhmm(start_text)
    end = _parse_hhmm(end_text)
    if start >= end:
        raise ValueError(f"invalid time range {value!r}")
    return start, end


def _parse_power(value: str, function: str) -> tuple[int | None, bool]:
    """Parse the power field into a power value and an ignored-input flag.

    Self-consumption carries no power on the device (`FI` is an empty object when
    F=3), so any value on such a row is a typo. It is dropped instead of
    rejecting the whole plan, and the second return value lets the caller decide
    whether to warn.

    Raises:
        ValueError: A non self-consumption row has a non-integer power, or a
            value outside 0 to 2500 W.
    """
    if function == LAKE6_TOU_TEXT_FUNCTION_SELF:
        return None, value not in ("", LAKE6_TOU_TEXT_POWER_PLACEHOLDER)
    if not value.isdigit():
        raise ValueError(f"invalid power {value!r}")
    power = int(value)
    if not LAKE6_TOU_POWER_MIN <= power <= LAKE6_TOU_POWER_MAX:
        raise ValueError(f"invalid power {value!r}")
    return power, False


def _parse_enabled(value: str) -> bool:
    """Parse the enabled flag, accepting on/off, true/false and yes/no besides 1/0.

    Raises:
        ValueError: The boolean spelling is not recognized.
    """
    normalized = value.strip().lower()
    if normalized in _TRUE_FLAGS:
        return True
    if normalized in _FALSE_FLAGS:
        return False
    raise ValueError(f"invalid enabled flag {value!r}")


def _parse_row(chunk: str) -> Lake6TouPlanRow:
    """Parse one line, i.e. one rule.

    Raises:
        ValueError: The rule does not have five fields, or a field is invalid.
    """
    fields = [field.strip() for field in chunk.split(LAKE6_TOU_TEXT_FIELD_SEPARATOR)]
    if len(fields) != 5:
        raise ValueError(f"a rule needs 5 fields, got {len(fields)}: {chunk!r}")
    start, end = _parse_time_range(fields[0])
    function = fields[1].lower()
    if function not in LAKE6_TOU_TEXT_FUNCTION_TO_CODE:
        raise ValueError(f"unknown function {fields[1]!r}")
    power, power_ignored = _parse_power(fields[2], function)
    return Lake6TouPlanRow(
        enabled=_parse_enabled(fields[4]),
        weekdays=parse_weekdays(fields[3]),
        start=start,
        end=end,
        function=function,
        power=power,
        power_ignored=power_ignored,
    )


def _format_rule(rule: Lake6TouRule) -> str | None:
    """Render one rule, or return None when a field is missing."""
    if rule.start is None or rule.end is None or rule.start >= rule.end:
        return None
    function = LAKE6_TOU_STATE_TO_TEXT_FUNCTION.get(rule.function or "")
    if function is None:
        return None
    if function == LAKE6_TOU_TEXT_FUNCTION_SELF:
        power = LAKE6_TOU_TEXT_POWER_PLACEHOLDER
    elif (
        rule.power is None
        or not LAKE6_TOU_POWER_MIN <= rule.power <= LAKE6_TOU_POWER_MAX
    ):
        return None
    else:
        power = str(rule.power)
    return LAKE6_TOU_TEXT_FIELD_SEPARATOR.join(
        (
            f"{rule.start}-{rule.end}",
            function,
            power,
            format_weekdays(rule.weekdays),
            "1" if rule.enabled else "0",
        )
    )


def _apply_row(entry: dict[str, Any], row: Lake6TouPlanRow) -> None:
    """Write one rule into a `time_cfg` entry in place."""
    entry["E"] = "1" if row.enabled else "0"
    entry["W"] = row.weekdays

    slot: dict[str, Any] = {}
    raw_slots = entry.get("TM")
    extra_slots: list[Any] = []
    if isinstance(raw_slots, list) and raw_slots:
        if isinstance(raw_slots[0], dict):
            # Reuse the existing object so unparsed keys survive.
            slot = raw_slots[0]
        extra_slots = raw_slots[1:]
    slot["T"] = f"{row.start.replace(':', '')}{row.end.replace(':', '')}"
    slot["F"] = LAKE6_TOU_TEXT_FUNCTION_TO_CODE[row.function]
    if row.function == LAKE6_TOU_TEXT_FUNCTION_SELF:
        # The device ignores power when F=3 and expects an empty object.
        slot["FI"] = {}
    else:
        params = slot.get("FI")
        if not isinstance(params, dict):
            params = {}
        params["P"] = str(row.power)
        # The firmware forces GC and GD to 1 and ignores any written value, but
        # it only carries GC with F=1 and GD with F=2. Rebuild both instead of
        # carrying the permit of a previous function across a function change.
        permit = LAKE6_TOU_TEXT_FUNCTION_TO_PERMIT[row.function]
        for key in LAKE6_TOU_PERMIT_KEYS:
            if key == permit:
                params[key] = 1
            else:
                params.pop(key, None)
        slot["FI"] = params
    # The device can hold several slots for one weekday set, but the text form
    # only shows the first as a rule. Keep the rest so editing that rule does
    # not wipe windows the integration never displayed.
    entry["TM"] = [slot, *extra_slots]
