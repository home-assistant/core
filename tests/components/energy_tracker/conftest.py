"""Common fixtures for Energy Tracker tests."""

from __future__ import annotations

import pytest




@pytest.fixture
def api_token() -> str:
    """Return a test API token."""
    return "test-token-12345678"


@pytest.fixture
def device_id() -> str:
    """Return a valid UUID device ID."""
    return "12345678-1234-1234-1234-123456789abc"
