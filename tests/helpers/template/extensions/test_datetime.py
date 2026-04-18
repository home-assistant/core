"""Test datetime template functions."""

from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from freezegun import freeze_time
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.util import dt as dt_util
from homeassistant.util.read_only_dict import ReadOnlyDict

from tests.helpers.template.helpers import render, render_to_info


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ([1, 2], False),
        ({1, 2}, False),
        ({"a": 1, "b": 2}, False),
        (ReadOnlyDict({"a": 1, "b": 2}), False),
        (MappingProxyType({"a": 1, "b": 2}), False),
        ("abc", False),
        (b"abc", False),
        ((1, 2), False),
        (datetime(2024, 1, 1, 0, 0, 0), True),
    ],
)
def test_is_datetime(hass: HomeAssistant, value, expected) -> None:
    """Test is datetime."""
    assert render(hass, "{{ value is datetime }}", {"value": value}) == expected


def test_strptime(hass: HomeAssistant) -> None:
    """Test the parse timestamp method."""
    tests = [
        ("2016-10-19 15:22:05.588122 UTC", "%Y-%m-%d %H:%M:%S.%f %Z", None),
        ("2016-10-19 15:22:05.588122+0100", "%Y-%m-%d %H:%M:%S.%f%z", None),
        ("2016-10-19 15:22:05.588122", "%Y-%m-%d %H:%M:%S.%f", None),
        ("2016-10-19", "%Y-%m-%d", None),
        ("2016", "%Y", None),
        ("15:22:05", "%H:%M:%S", None),
    ]

    for inp, fmt, expected in tests:
        if expected is None:
            expected = str(datetime.strptime(inp, fmt))

        temp = f"{{{{ strptime('{inp}', '{fmt}') }}}}"

        assert render(hass, temp) == expected

    # Test handling of invalid input
    invalid_tests = [
        ("1469119144", "%Y"),
        ("invalid", "%Y"),
    ]

    for inp, fmt in invalid_tests:
        temp = f"{{{{ strptime('{inp}', '{fmt}') }}}}"

        with pytest.raises(TemplateError):
            render(hass, temp)

    # Test handling of default return value
    assert render(hass, "{{ strptime('invalid', '%Y', 1) }}") == 1
    assert render(hass, "{{ strptime('invalid', '%Y', default=1) }}") == 1


async def test_timestamp_custom(hass: HomeAssistant) -> None:
    """Test the timestamps to custom filter."""
    await hass.config.async_set_time_zone("UTC")
    now = dt_util.utcnow()
    tests = [
        (1469119144, None, True, "2016-07-21 16:39:04"),
        (1469119144, "%Y", True, 2016),
        (1469119144, "invalid", True, "invalid"),
        (dt_util.as_timestamp(now), None, False, now.strftime("%Y-%m-%d %H:%M:%S")),
    ]

    for inp, fmt, local, out in tests:
        if fmt:
            fil = f"timestamp_custom('{fmt}')"
        elif fmt and local:
            fil = f"timestamp_custom('{fmt}', {local})"
        else:
            fil = "timestamp_custom"

        assert render(hass, f"{{{{ {inp} | {fil} }}}}") == out

    # Test handling of invalid input
    invalid_tests = [
        (None, None, None),
    ]

    for inp, fmt, local in invalid_tests:
        if fmt:
            fil = f"timestamp_custom('{fmt}')"
        elif fmt and local:
            fil = f"timestamp_custom('{fmt}', {local})"
        else:
            fil = "timestamp_custom"

        with pytest.raises(TemplateError):
            render(hass, f"{{{{ {inp} | {fil} }}}}")

    # Test handling of default return value
    assert render(hass, "{{ None | timestamp_custom('invalid', True, 1) }}") == 1
    assert render(hass, "{{ None | timestamp_custom(default=1) }}") == 1


async def test_timestamp_local(hass: HomeAssistant) -> None:
    """Test the timestamps to local filter."""
    await hass.config.async_set_time_zone("UTC")
    tests = [
        (1469119144, "2016-07-21T16:39:04+00:00"),
    ]

    for inp, out in tests:
        assert render(hass, f"{{{{ {inp} | timestamp_local }}}}") == out

    # Test handling of invalid input
    invalid_tests = [
        None,
    ]

    for inp in invalid_tests:
        with pytest.raises(TemplateError):
            render(hass, f"{{{{ {inp} | timestamp_local }}}}")

    # Test handling of default return value
    assert render(hass, "{{ None | timestamp_local(1) }}") == 1
    assert render(hass, "{{ None | timestamp_local(default=1) }}") == 1


@pytest.mark.parametrize(
    "input",
    [
        "2021-06-03 13:00:00.000000+00:00",
        "1986-07-09T12:00:00Z",
        "2016-10-19 15:22:05.588122+0100",
        "2016-10-19",
        "2021-01-01 00:00:01",
        "invalid",
    ],
)
def test_as_datetime(hass: HomeAssistant, input) -> None:
    """Test converting a timestamp string to a date object."""
    expected = dt_util.parse_datetime(input)
    if expected is not None:
        expected = str(expected)
    assert render(hass, f"{{{{ as_datetime('{input}') }}}}") == expected
    assert render(hass, f"{{{{ '{input}' | as_datetime }}}}") == expected


@pytest.mark.parametrize(
    ("input", "output"),
    [
        (1469119144, "2016-07-21 16:39:04+00:00"),
        (1469119144.0, "2016-07-21 16:39:04+00:00"),
        (-1, "1969-12-31 23:59:59+00:00"),
    ],
)
def test_as_datetime_from_timestamp(
    hass: HomeAssistant,
    input: float,
    output: str,
) -> None:
    """Test converting a UNIX timestamp to a date object."""
    assert render(hass, f"{{{{ as_datetime({input}) }}}}") == output
    assert render(hass, f"{{{{ {input} | as_datetime }}}}") == output
    assert render(hass, f"{{{{ as_datetime('{input}') }}}}") == output
    assert render(hass, f"{{{{ '{input}' | as_datetime }}}}") == output


@pytest.mark.parametrize(
    ("input", "output"),
    [
        (
            "{% set dt = as_datetime('2024-01-01 16:00:00-08:00') %}",
            "2024-01-01 16:00:00-08:00",
        ),
        (
            "{% set dt = as_datetime('2024-01-29').date() %}",
            "2024-01-29 00:00:00",
        ),
    ],
)
def test_as_datetime_from_datetime(
    hass: HomeAssistant, input: str, output: str
) -> None:
    """Test using datetime.datetime or datetime.date objects as input."""

    assert render(hass, f"{input}{{{{ dt | as_datetime }}}}") == output

    assert render(hass, f"{input}{{{{ as_datetime(dt) }}}}") == output


@pytest.mark.parametrize(
    ("input", "default", "output"),
    [
        (1469119144, 123, "2016-07-21 16:39:04+00:00"),
        ('"invalid"', ["default output"], ["default output"]),
        (["a", "list"], 0, 0),
        ({"a": "dict"}, None, None),
    ],
)
def test_as_datetime_default(
    hass: HomeAssistant, input: Any, default: Any, output: str
) -> None:
    """Test invalid input and return default value."""

    assert render(hass, f"{{{{ as_datetime({input}, default={default}) }}}}") == output
    assert render(hass, f"{{{{ {input} | as_datetime({default}) }}}}") == output


def test_as_local(hass: HomeAssistant) -> None:
    """Test converting time to local."""

    hass.states.async_set("test.object", "available")
    last_updated = hass.states.get("test.object").last_updated
    assert render(hass, "{{ as_local(states.test.object.last_updated) }}") == str(
        dt_util.as_local(last_updated)
    )
    assert render(hass, "{{ states.test.object.last_updated | as_local }}") == str(
        dt_util.as_local(last_updated)
    )


def test_timestamp_utc(hass: HomeAssistant) -> None:
    """Test the timestamps to local filter."""
    now = dt_util.utcnow()
    tests = [
        (1469119144, "2016-07-21T16:39:04+00:00"),
        (dt_util.as_timestamp(now), now.isoformat()),
    ]

    for inp, out in tests:
        assert render(hass, f"{{{{ {inp} | timestamp_utc }}}}") == out

    # Test handling of invalid input
    invalid_tests = [
        None,
    ]

    for inp in invalid_tests:
        with pytest.raises(TemplateError):
            render(hass, f"{{{{ {inp} | timestamp_utc }}}}")

    # Test handling of default return value
    assert render(hass, "{{ None | timestamp_utc(1) }}") == 1
    assert render(hass, "{{ None | timestamp_utc(default=1) }}") == 1


def test_as_timestamp(hass: HomeAssistant) -> None:
    """Test the as_timestamp function."""
    with pytest.raises(TemplateError):
        render(hass, '{{ as_timestamp("invalid") }}')

    hass.states.async_set("test.object", None)
    with pytest.raises(TemplateError):
        render(hass, "{{ as_timestamp(states.test.object) }}")

    tpl = (
        '{{ as_timestamp(strptime("2024-02-03T09:10:24+0000", '
        '"%Y-%m-%dT%H:%M:%S%z")) }}'
    )
    assert render(hass, tpl) == 1706951424.0

    # Test handling of default return value
    assert render(hass, "{{ 'invalid' | as_timestamp(1) }}") == 1
    assert render(hass, "{{ 'invalid' | as_timestamp(default=1) }}") == 1
    assert render(hass, "{{ as_timestamp('invalid', 1) }}") == 1
    assert render(hass, "{{ as_timestamp('invalid', default=1) }}") == 1


def test_as_timedelta(hass: HomeAssistant) -> None:
    """Test the as_timedelta function/filter."""

    result = render(hass, "{{ as_timedelta('PT10M') }}")
    assert result == "0:10:00"

    result = render(hass, "{{ 'PT10M' | as_timedelta }}")
    assert result == "0:10:00"

    result = render(hass, "{{ 'T10M' | as_timedelta }}")
    assert result is None


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
def test_now(mock_is_safe, hass: HomeAssistant) -> None:
    """Test now method."""
    now = dt_util.now()
    with freeze_time(now):
        info = render_to_info(hass, "{{ now().isoformat() }}")
        assert now.isoformat() == info.result()

    assert info.has_time is True


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
def test_utcnow(mock_is_safe, hass: HomeAssistant) -> None:
    """Test now method."""
    utcnow = dt_util.utcnow()
    with freeze_time(utcnow):
        info = render_to_info(hass, "{{ utcnow().isoformat() }}")
        assert utcnow.isoformat() == info.result()

    assert info.has_time is True


@pytest.mark.parametrize(
    ("now", "expected", "expected_midnight", "timezone_str"),
    [
        # Host clock in UTC
        (
            "2021-11-24 03:00:00+00:00",
            "2021-11-23T10:00:00-08:00",
            "2021-11-23T00:00:00-08:00",
            "America/Los_Angeles",
        ),
        # Host clock in local time
        (
            "2021-11-23 19:00:00-08:00",
            "2021-11-23T10:00:00-08:00",
            "2021-11-23T00:00:00-08:00",
            "America/Los_Angeles",
        ),
    ],
)
@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
async def test_today_at(
    mock_is_safe, hass: HomeAssistant, now, expected, expected_midnight, timezone_str
) -> None:
    """Test today_at method."""
    freezer = freeze_time(now)
    freezer.start()

    await hass.config.async_set_time_zone(timezone_str)

    result = render(hass, "{{ today_at('10:00').isoformat() }}")
    assert result == expected

    result = render(hass, "{{ today_at('10:00:00').isoformat() }}")
    assert result == expected

    result = render(hass, "{{ ('10:00:00' | today_at).isoformat() }}")
    assert result == expected

    result = render(hass, "{{ today_at().isoformat() }}")
    assert result == expected_midnight

    with pytest.raises(TemplateError):
        render(hass, "{{ today_at('bad') }}")

    info = render_to_info(hass, "{{ today_at('10:00').isoformat() }}")
    assert info.has_time is True

    freezer.stop()


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
async def test_relative_time(mock_is_safe, hass: HomeAssistant) -> None:
    """Test relative_time method."""
    await hass.config.async_set_time_zone("UTC")
    now = datetime.strptime("2000-01-01 10:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
    relative_time_template = (
        '{{relative_time(strptime("2000-01-01 09:00:00", "%Y-%m-%d %H:%M:%S"))}}'
    )
    with freeze_time(now):
        result = render(hass, relative_time_template)
        assert result == "1 hour"
        result = render(
            hass,
            (
                "{{"
                "  relative_time("
                "    strptime("
                '        "2000-01-01 09:00:00 +01:00",'
                '        "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "2 hours"

        result = render(
            hass,
            (
                "{{"
                "  relative_time("
                "    strptime("
                '       "2000-01-01 03:00:00 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "1 hour"

        result1 = str(
            datetime.strptime("2000-01-01 11:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
        )
        result2 = render(
            hass,
            (
                "{{"
                "  relative_time("
                "    strptime("
                '       "2000-01-01 11:00:00 +00:00",'
                '       "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result1 == result2

        result = render(hass, '{{relative_time("string")}}')
        assert result == "string"

        # Test behavior when current time is same as the input time
        result = render(
            hass,
            (
                "{{"
                "  relative_time("
                "    strptime("
                '        "2000-01-01 10:00:00 +00:00",'
                '        "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "0 seconds"

        # Test behavior when the input time is in the future
        result = render(
            hass,
            (
                "{{"
                "  relative_time("
                "    strptime("
                '        "2000-01-01 11:00:00 +00:00",'
                '        "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "2000-01-01 11:00:00+00:00"

        info = render_to_info(hass, relative_time_template)
        assert info.has_time is True


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
async def test_time_since(mock_is_safe, hass: HomeAssistant) -> None:
    """Test time_since method."""
    await hass.config.async_set_time_zone("UTC")
    now = datetime.strptime("2000-01-01 10:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
    time_since_template = (
        '{{time_since(strptime("2000-01-01 09:00:00", "%Y-%m-%d %H:%M:%S"))}}'
    )
    with freeze_time(now):
        result = render(hass, time_since_template)
        assert result == "1 hour"

        result = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '        "2000-01-01 09:00:00 +01:00",'
                '        "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "2 hours"

        result = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '       "2000-01-01 03:00:00 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "1 hour"

        result1 = str(
            datetime.strptime("2000-01-01 11:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
        )
        result2 = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '       "2000-01-01 11:00:00 +00:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "    precision = 2"
                "  )"
                "}}"
            ),
        )
        assert result1 == result2

        result = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '        "2000-01-01 09:05:00 +01:00",'
                '        "%Y-%m-%d %H:%M:%S %z"),'
                "       precision=2"
                "  )"
                "}}"
            ),
        )
        assert result == "1 hour 55 minutes"

        result = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '       "2000-01-01 02:05:27 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "       precision = 3"
                "  )"
                "}}"
            ),
        )
        assert result == "1 hour 54 minutes 33 seconds"
        result = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '       "2000-01-01 02:05:27 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z")'
                "  )"
                "}}"
            ),
        )
        assert result == "2 hours"
        result = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '       "1999-02-01 02:05:27 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "       precision = 0"
                "  )"
                "}}"
            ),
        )
        assert result == "11 months 4 days 1 hour 54 minutes 33 seconds"
        result = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '       "1999-02-01 02:05:27 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z")'
                "  )"
                "}}"
            ),
        )
        assert result == "11 months"
        result1 = str(
            datetime.strptime("2000-01-01 11:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
        )
        result2 = render(
            hass,
            (
                "{{"
                "  time_since("
                "    strptime("
                '       "2000-01-01 11:00:00 +00:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "       precision=3"
                "  )"
                "}}"
            ),
        )
        assert result1 == result2

        result = render(hass, '{{time_since("string")}}')
        assert result == "string"

        info = render_to_info(hass, time_since_template)
        assert info.has_time is True


@patch(
    "homeassistant.helpers.template.TemplateEnvironment.is_safe_callable",
    return_value=True,
)
async def test_time_until(mock_is_safe, hass: HomeAssistant) -> None:
    """Test time_until method."""
    await hass.config.async_set_time_zone("UTC")
    now = datetime.strptime("2000-01-01 10:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
    time_until_template = (
        '{{time_until(strptime("2000-01-01 11:00:00", "%Y-%m-%d %H:%M:%S"))}}'
    )
    with freeze_time(now):
        result = render(hass, time_until_template)
        assert result == "1 hour"

        result = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '        "2000-01-01 13:00:00 +01:00",'
                '        "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "2 hours"

        result = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '       "2000-01-01 05:00:00 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"'
                "    )"
                "  )"
                "}}"
            ),
        )
        assert result == "1 hour"

        result1 = str(
            datetime.strptime("2000-01-01 09:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
        )
        result2 = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '       "2000-01-01 09:00:00 +00:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "    precision = 2"
                "  )"
                "}}"
            ),
        )
        assert result1 == result2

        result = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '        "2000-01-01 12:05:00 +01:00",'
                '        "%Y-%m-%d %H:%M:%S %z"),'
                "       precision=2"
                "  )"
                "}}"
            ),
        )
        assert result == "1 hour 5 minutes"

        result = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '       "2000-01-01 05:54:33 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "       precision = 3"
                "  )"
                "}}"
            ),
        )
        assert result == "1 hour 54 minutes 33 seconds"
        result = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '       "2000-01-01 05:54:33 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z")'
                "  )"
                "}}"
            ),
        )
        assert result == "2 hours"
        result = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '       "2001-02-01 05:54:33 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "       precision = 0"
                "  )"
                "}}"
            ),
        )
        assert result == "1 year 1 month 2 days 1 hour 54 minutes 33 seconds"
        result = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '       "2001-02-01 05:54:33 -06:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "       precision = 4"
                "  )"
                "}}"
            ),
        )
        assert result == "1 year 1 month 2 days 2 hours"
        result1 = str(
            datetime.strptime("2000-01-01 09:00:00 +00:00", "%Y-%m-%d %H:%M:%S %z")
        )
        result2 = render(
            hass,
            (
                "{{"
                "  time_until("
                "    strptime("
                '       "2000-01-01 09:00:00 +00:00",'
                '       "%Y-%m-%d %H:%M:%S %z"),'
                "       precision=3"
                "  )"
                "}}"
            ),
        )
        assert result1 == result2

        result = render(hass, '{{time_until("string")}}')
        assert result == "string"

        info = render_to_info(hass, time_until_template)
        assert info.has_time is True
