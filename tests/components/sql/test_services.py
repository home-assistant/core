"""Tests for the SQL integration services."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest
import voluptuous as vol
from voluptuous import MultipleInvalid

from homeassistant.components.recorder import Recorder
from homeassistant.components.sql.const import DOMAIN
from homeassistant.components.sql.services import SERVICE_QUERY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.components.recorder.common import async_wait_recording_done


async def test_query_service_recorder_db(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test the query service with the default recorder database."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Populate the recorder database with some data
    hass.states.async_set("sensor.test", "123", {"attr": "value"})
    hass.states.async_set("sensor.test2", "456")
    await async_wait_recording_done(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_QUERY,
        {
            "query": (
                "SELECT states_meta.entity_id, states.state "
                "FROM states INNER JOIN states_meta ON states.metadata_id = states_meta.metadata_id "
                "WHERE states_meta.entity_id LIKE 'sensor.test%' ORDER BY states_meta.entity_id"
            )
        },
        blocking=True,
        return_response=True,
    )

    assert response == {
        "result": [
            {"entity_id": "sensor.test", "state": "123"},
            {"entity_id": "sensor.test2", "state": "456"},
        ]
    }


async def test_query_service_external_db(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test the query service with an external database via db_url."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    # Create and populate the external database
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (name TEXT, age INTEGER)")
    conn.execute("INSERT INTO users (name, age) VALUES ('Alice', 30), ('Bob', 25)")
    conn.commit()
    conn.close()

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_QUERY,
        {"query": "SELECT name, age FROM users ORDER BY age", "db_url": db_url},
        blocking=True,
        return_response=True,
    )

    assert response == {
        "result": [
            {"name": "Bob", "age": 25},
            {"name": "Alice", "age": 30},
        ]
    }


async def test_query_service_data_conversion(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test the query service correctly converts data types."""
    db_path = tmp_path / "test_types.db"
    db_url = f"sqlite:///{db_path}"

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE data (id INTEGER, cost DECIMAL(10, 2), event_date DATE, raw BLOB)"
    )
    conn.execute(
        "INSERT INTO data (id, cost, event_date, raw) VALUES (1, 199.99, '2023-01-15', X'DEADBEEF')"
    )
    conn.commit()
    conn.close()

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_QUERY,
        {"query": "SELECT * FROM data", "db_url": db_url},
        blocking=True,
        return_response=True,
    )

    assert response == {
        "result": [
            {
                "id": 1,
                "cost": 199.99,  # Converted from Decimal to float
                "event_date": "2023-01-15",  # Converted from date to ISO string
                "raw": "0xdeadbeef",  # Converted from bytes to hex string
            }
        ]
    }


async def test_query_service_no_results(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test the query service when a query returns no results."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_QUERY,
        {"query": "SELECT * FROM states"},
        blocking=True,
        return_response=True,
    )

    assert response == {"result": []}


async def test_query_service_invalid_query_not_select(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test the service rejects non-SELECT queries."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(vol.Invalid, match="Only SELECT queries allowed"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_QUERY,
            {"query": "UPDATE states SET state = 'hacked'"},
            blocking=True,
            return_response=True,
        )


async def test_query_service_sqlalchemy_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test the service handles SQLAlchemy errors during query execution."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(MultipleInvalid, match="Invalid SQL query"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_QUERY,
            # Syntactically incorrect query
            {"query": "SELEC * FROM states"},
            blocking=True,
            return_response=True,
        )


async def test_query_service_invalid_db_url(hass: HomeAssistant) -> None:
    """Test the service handles an invalid database URL."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.sql.util._validate_and_get_session_maker_for_db_url",
            return_value=None,
        ),
        pytest.raises(
            ServiceValidationError, match="Failed to connect to the database"
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_QUERY,
            {
                "query": "SELECT 1",
                "db_url": "postgresql://user:pass@host:123/dbname",
            },
            blocking=True,
            return_response=True,
        )


async def test_query_service_performance_issue_validation(
    recorder_mock: Recorder,
    hass: HomeAssistant,
) -> None:
    """Test the service validates queries against the recorder for performance issues."""
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(
        ServiceValidationError,
        match="The provided query is not allowed: Query contains entity_id but does not reference states_meta",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_QUERY,
            {"query": "SELECT entity_id FROM states"},
            blocking=True,
            return_response=True,
        )
