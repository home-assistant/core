"""Test the sql utils."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import voluptuous as vol

from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.sql.util import (
    convert_value,
    resolve_db_url,
    validate_sql_select,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template


async def test_resolve_db_url_when_none_configured(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test return recorder db_url if provided db_url is None."""
    db_url = None
    resolved_url = resolve_db_url(hass, db_url)

    assert resolved_url == get_instance(hass).db_url


async def test_resolve_db_url_when_configured(hass: HomeAssistant) -> None:
    """Test return provided db_url if it's set."""
    db_url = "mssql://"
    resolved_url = resolve_db_url(hass, db_url)

    assert resolved_url == db_url


@pytest.mark.parametrize(
    ("sql_query", "expected_error_message"),
    [
        (
            "DROP TABLE *",
            "SQL query must be of type SELECT",
        ),
        (
            "SELECT5 as value",
            "SQL query is empty or unknown type",
        ),
        (
            ";;",
            "SQL query is empty or unknown type",
        ),
        (
            "UPDATE states SET state = 999999 WHERE state_id = 11125",
            "SQL query must be of type SELECT",
        ),
        (
            "WITH test AS (SELECT state FROM states) UPDATE states SET states.state = test.state;",
            "SQL query must be of type SELECT",
        ),
        (
            "SELECT 5 as value; UPDATE states SET state = 10;",
            "Multiple SQL statements are not allowed",
        ),
    ],
)
async def test_invalid_sql_queries(
    hass: HomeAssistant,
    sql_query: str,
    expected_error_message: str,
) -> None:
    """Test that various invalid or disallowed SQL queries raise the correct exception."""
    with pytest.raises(vol.Invalid, match=expected_error_message):
        validate_sql_select(Template(sql_query, hass))


@pytest.mark.parametrize(
    ("input", "expected_output"),
    [
        (Decimal("199.99"), 199.99),
        (date(2023, 1, 15), "2023-01-15"),
        (datetime(2023, 1, 15, 12, 30, 45, tzinfo=UTC), "2023-01-15T12:30:45+00:00"),
        (b"\xde\xad\xbe\xef", "0xdeadbeef"),
        ("deadbeef", "deadbeef"),
        (199.99, 199.99),
        (69, 69),
    ],
)
async def test_value_conversion(
    input: Decimal | date | datetime | bytes | str | float,
    expected_output: str | float,
) -> None:
    """Test value conversion."""
    assert convert_value(input) == expected_output
