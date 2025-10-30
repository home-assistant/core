"""Test the sql utils."""

from datetime import date
from decimal import Decimal

import pytest
import voluptuous as vol

from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.sql.util import (
    ensure_serializable,
    resolve_db_url,
    validate_sql_select,
)
from homeassistant.core import HomeAssistant


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
            "Only SELECT queries allowed",
        ),
        (
            "SELECT5 as value",
            "Invalid SQL query",
        ),
        (
            ";;",
            "Invalid SQL query",
        ),
        (
            "UPDATE states SET state = 999999 WHERE state_id = 11125",
            "Only SELECT queries allowed",
        ),
        (
            "WITH test AS (SELECT state FROM states) UPDATE states SET states.state = test.state;",
            "Only SELECT queries allowed",
        ),
        (
            "SELECT 5 as value; UPDATE states SET state = 10;",
            "Multiple SQL queries are not supported",
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
        validate_sql_select(sql_query)


@pytest.mark.parametrize(
    ("input", "expected_output"),
    [
        (Decimal("199.99"), 199.99),
        (date(2023, 1, 15), "2023-01-15"),
        (b"\xde\xad\xbe\xef", "0xdeadbeef"),
        ("deadbeef", "deadbeef"),
        (199.99, 199.99),
        (69, 69),
    ],
)
async def test_data_conversion(
    input: Decimal | date | bytes | str | float,
    expected_output: str | float,
) -> None:
    """Test data conversion to serializable type."""
    assert ensure_serializable(input) == expected_output
