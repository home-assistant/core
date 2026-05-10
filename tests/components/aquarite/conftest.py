"""Shared fixtures for Aquarite tests."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.components.aquarite.const import DOMAIN

from tests.common import load_json_object_fixture

MOCK_USERNAME = "testuser@example.com"
MOCK_PASSWORD = "testpassword"
MOCK_USER_ID = "firebase-uid-testuser"
MOCK_POOL_ID = "ABCDEF1234567890"
MOCK_POOL_NAME = "My Pool"


@pytest.fixture
def mock_pool_data() -> dict[str, Any]:
    """Return mock coordinator pool data loaded from the JSON fixture."""
    return load_json_object_fixture("pool_data.json", DOMAIN)
