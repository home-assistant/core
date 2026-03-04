"""Fixtures for the EOL Tracker integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.eol_tracker import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.eol_tracker.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Python",
        domain=DOMAIN,
        data={
            "input_device": "https://endoflife.date/api/v1/products/python/releases/latest"
        },
        unique_id="https://endoflife.date/api/v1/products/python/releases/latest",
    )
