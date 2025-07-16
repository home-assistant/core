"""Test the sql utils."""

import pytest
import voluptuous as vol

from homeassistant.components.recorder import Recorder, get_instance
from homeassistant.components.sql.util import resolve_db_url, validate_sql_select
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


async def test_invalid_query(hass: HomeAssistant) -> None:
    """Test invalid query."""
    with pytest.raises(vol.Invalid, match="Only SELECT queries allowed"):
        validate_sql_select("DROP TABLE *")

    with pytest.raises(vol.Invalid, match="Invalid SQL query"):
        validate_sql_select("SELECT5 as value")

    with pytest.raises(vol.Invalid, match="Invalid SQL query"):
        validate_sql_select(";;")


async def test_query_no_read_only(hass: HomeAssistant) -> None:
    """Test query no read only."""
    with pytest.raises(vol.Invalid, match="Only SELECT queries allowed"):
        validate_sql_select("UPDATE states SET state = 999999 WHERE state_id = 11125")


async def test_query_no_read_only_cte(hass: HomeAssistant) -> None:
    """Test query no read only CTE."""
    with pytest.raises(vol.Invalid, match="Only SELECT queries allowed"):
        validate_sql_select(
            "WITH test AS (SELECT state FROM states) UPDATE states SET states.state = test.state;"
        )


async def test_multiple_queries(hass: HomeAssistant) -> None:
    """Test multiple queries."""
    with pytest.raises(vol.Invalid, match="Multiple SQL queries are not supported"):
        validate_sql_select("SELECT 5 as value; UPDATE states SET state = 10;")
