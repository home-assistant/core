"""Test the APsystems Lake_6 time-of-use text format."""

import pytest

from homeassistant.components.apsystems.lake6.client import Lake6TouRule
from homeassistant.components.apsystems.lake6.const import LAKE6_TOU_TEXT_MAX_RULES
from homeassistant.components.apsystems.lake6.tou import (
    Lake6TouPlanRow,
    build_payload,
    format_weekdays,
    parse_plan,
    parse_weekdays,
    render_plan,
)

PLAN = "09:00-09:10|discharge|200|12345|1;10:00-10:10|self|-|67|1"


@pytest.mark.parametrize(
    ("weekdays", "expected"),
    [
        pytest.param([1, 2, 3, 4, 5], "12345", id="sorted"),
        pytest.param([5, 1, 1, 3], "135", id="deduplicated"),
        pytest.param([], "", id="empty"),
    ],
)
def test_format_weekdays(weekdays: list[int], expected: str) -> None:
    """Test the weekday list is rendered compactly."""
    assert format_weekdays(weekdays) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("12345", [1, 2, 3, 4, 5], id="compact"),
        pytest.param("1-5", [1, 2, 3, 4, 5], id="range"),
        pytest.param("1,3,5", [1, 3, 5], id="list"),
        pytest.param("1-3,6", [1, 2, 3, 6], id="mixed"),
        pytest.param(" 2 1 ", [1, 2], id="whitespace"),
        pytest.param("", [], id="empty"),
    ],
)
def test_parse_weekdays(value: str, expected: list[int]) -> None:
    """Test the compact, range and list forms are all accepted."""
    assert parse_weekdays(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0", id="zero"),
        pytest.param("8", id="above-seven"),
        pytest.param("5-1", id="reversed-range"),
        pytest.param("a", id="not-a-digit"),
        pytest.param("12-3", id="multi-digit-range-end"),
    ],
)
def test_parse_weekdays_invalid(value: str) -> None:
    """Test an unusable weekday field raises."""
    with pytest.raises(ValueError):
        parse_weekdays(value)


def test_parse_plan() -> None:
    """Test both a charged rule and a self-consumption rule parse."""
    rows = parse_plan(PLAN)

    assert rows == [
        Lake6TouPlanRow(
            enabled=True,
            weekdays=[1, 2, 3, 4, 5],
            start="09:00",
            end="09:10",
            function="discharge",
            power=200,
        ),
        Lake6TouPlanRow(
            enabled=True,
            weekdays=[6, 7],
            start="10:00",
            end="10:10",
            function="self",
            power=None,
        ),
    ]


def test_parse_plan_ignores_power_on_self_consumption() -> None:
    """Test a power value on a self-consumption row is dropped, not rejected."""
    rows = parse_plan("10:00-10:10|self|200|1|0")

    assert rows[0].power is None
    assert rows[0].power_ignored is True
    assert rows[0].enabled is False


@pytest.mark.parametrize(
    ("value", "message"),
    [
        pytest.param("", "plan is empty", id="empty"),
        pytest.param("09:00-09:10|charge|200|1", "needs 5 fields", id="short-row"),
        pytest.param("09:00|charge|200|1|1", "invalid time", id="bad-time"),
        pytest.param("09:10-09:00|charge|200|1|1", "invalid time range", id="reversed"),
        pytest.param("09:00-09:10|charge|x|1|1", "invalid power", id="bad-power"),
        pytest.param("09:00-09:10|charge|2501|1|1", "invalid power", id="power-high"),
        pytest.param("09:00-09:10|hold|200|1|1", "unknown function", id="function"),
        pytest.param("09:00-09:10|charge|200|1|maybe", "invalid enabled", id="enabled"),
    ],
)
def test_parse_plan_invalid(value: str, message: str) -> None:
    """Test an unusable plan raises with a readable reason."""
    with pytest.raises(ValueError, match=message):
        parse_plan(value)


def test_parse_plan_too_many_rules() -> None:
    """Test more rules than the state length fits are rejected."""
    value = ";".join(["09:00-09:10|charge|200|1|1"] * (LAKE6_TOU_TEXT_MAX_RULES + 1))

    with pytest.raises(ValueError, match="at most"):
        parse_plan(value)


def test_render_plan() -> None:
    """Test the device rules are rendered back into the text form."""
    rules = [
        Lake6TouRule(
            enabled=True,
            weekdays=[1, 2, 3, 4, 5],
            start="09:00",
            end="09:10",
            function="discharge",
            power=200,
        ),
        Lake6TouRule(
            enabled=False,
            weekdays=[6, 7],
            start="10:00",
            end="10:10",
            function="self_consumption",
            power=None,
        ),
    ]

    assert (
        render_plan(rules)
        == "09:00-09:10|discharge|200|12345|1;10:00-10:10|self|-|67|0"
    )


def test_render_plan_round_trip() -> None:
    """Test rendering the parsed plan gives back the same text."""
    rules = [
        Lake6TouRule(
            enabled=True,
            weekdays=[1, 2, 3, 4, 5],
            start="09:00",
            end="09:10",
            function="discharge",
            power=200,
        ),
        Lake6TouRule(
            enabled=True,
            weekdays=[6, 7],
            start="10:00",
            end="10:10",
            function="self_consumption",
            power=None,
        ),
    ]

    assert render_plan(rules) == PLAN


@pytest.mark.parametrize(
    "rule",
    [
        pytest.param(
            Lake6TouRule(
                enabled=True,
                weekdays=[1],
                start=None,
                end="09:10",
                function="charge",
                power=200,
            ),
            id="missing-start",
        ),
        pytest.param(
            Lake6TouRule(
                enabled=True,
                weekdays=[1],
                start="09:10",
                end="09:00",
                function="charge",
                power=200,
            ),
            id="reversed",
        ),
        pytest.param(
            Lake6TouRule(
                enabled=True,
                weekdays=[1],
                start="09:00",
                end="09:10",
                function=None,
                power=200,
            ),
            id="unknown-function",
        ),
        pytest.param(
            Lake6TouRule(
                enabled=True,
                weekdays=[1],
                start="09:00",
                end="09:10",
                function="charge",
                power=2501,
            ),
            id="power-out-of-range",
        ),
    ],
)
def test_render_plan_returns_none(rule: Lake6TouRule) -> None:
    """Test a rule that cannot be expressed makes the whole plan unrenderable."""
    assert render_plan([rule]) is None


def test_build_payload_keeps_unparsed_keys() -> None:
    """Test keys the integration does not parse survive a write."""
    raw = [
        {
            "E": "1",
            "W": [1, 2, 3, 4, 5],
            "X": "keep",
            "TM": [
                {
                    "T": "09000910",
                    "F": "2",
                    "FI": {"P": "200", "GD": 1, "Z": "keep"},
                }
            ],
        }
    ]
    rows = [
        Lake6TouPlanRow(
            enabled=False,
            weekdays=[6],
            start="20:00",
            end="21:00",
            function="charge",
            power=500,
        )
    ]

    assert build_payload(raw, rows) == [
        {
            "E": "0",
            "W": [6],
            "X": "keep",
            "TM": [
                {
                    "T": "20002100",
                    "F": "1",
                    "FI": {"P": "500", "GC": 1, "Z": "keep"},
                }
            ],
        }
    ]


@pytest.mark.parametrize(
    ("function", "power", "code", "expected_fi"),
    [
        pytest.param("charge", 500, "1", {"P": "500", "GC": 1}, id="charge"),
        pytest.param("discharge", 400, "2", {"P": "400", "GD": 1}, id="discharge"),
        pytest.param("self", None, "3", {}, id="self-consumption"),
    ],
)
def test_build_payload_rebuilds_permits(
    function: str, power: int | None, code: str, expected_fi: dict[str, str | int]
) -> None:
    """Test GC and GD follow the function instead of the raw entry."""
    raw = [
        {
            "E": "1",
            "W": [1],
            "TM": [{"T": "09000910", "F": "2", "FI": {"P": "200", "GC": 1, "GD": 1}}],
        }
    ]
    rows = [
        Lake6TouPlanRow(
            enabled=True,
            weekdays=[1],
            start="09:00",
            end="09:10",
            function=function,
            power=power,
        )
    ]

    payload = build_payload(raw, rows)

    assert payload[0]["TM"] == [{"T": "09000910", "F": code, "FI": expected_fi}]


def test_build_payload_keeps_extra_slots() -> None:
    """Test editing a rule keeps the slots the text form cannot show."""
    extra = {"T": "18001900", "F": "3", "FI": {}}
    raw = [
        {
            "E": "1",
            "W": [1],
            "TM": [
                {"T": "09000910", "F": "2", "FI": {"P": "200", "GD": 1}},
                extra,
            ],
        }
    ]
    rows = parse_plan("09:00-09:10|discharge|300|1|1")

    payload = build_payload(raw, rows)

    assert payload[0]["TM"] == [
        {"T": "09000910", "F": "2", "FI": {"P": "300", "GD": 1}},
        extra,
    ]


def test_build_payload_adds_new_rows() -> None:
    """Test a row without a raw counterpart starts from an empty object."""
    rows = parse_plan(PLAN)

    assert build_payload([], rows) == [
        {
            "E": "1",
            "W": [1, 2, 3, 4, 5],
            "TM": [{"T": "09000910", "F": "2", "FI": {"P": "200", "GD": 1}}],
        },
        {"E": "1", "W": [6, 7], "TM": [{"T": "10001010", "F": "3", "FI": {}}]},
    ]
