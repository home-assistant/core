"""Fixtures for the SQL integration."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sql.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def create_db(
    hass: HomeAssistant,
    tmp_path: Path,
) -> str:
    """Test the SQL sensor with a query that returns no value."""
    db_path = tmp_path / "test.db"
    db_path_str = f"sqlite:///{db_path}"

    def make_test_db():
        """Create a test database."""
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE users (value INTEGER)")
        conn.commit()
        conn.close()

    await hass.async_add_executor_job(make_test_db)
    return db_path_str
