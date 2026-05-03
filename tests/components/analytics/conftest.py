"""Common fixtures for the analytics tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

MOCK_SNAPSHOT_PAYLOAD = {"mock_integration": {"devices": [], "entities": []}}


@pytest.fixture
def mock_snapshot_payload() -> Generator[None]:
    """Mock _async_snapshot_payload to return non-empty data."""
    with patch(
        "homeassistant.components.analytics.analytics._async_snapshot_payload",
        return_value=MOCK_SNAPSHOT_PAYLOAD,
    ):
        yield
