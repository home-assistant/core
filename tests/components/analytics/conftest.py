"""Common fixtures for the analytics tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from . import MOCK_SNAPSHOT_PAYLOAD


@pytest.fixture
def mock_snapshot_payload() -> Generator[None]:
    """Mock _async_snapshot_payload to return non-empty data."""
    with patch(
        "homeassistant.components.analytics.analytics._async_snapshot_payload",
        return_value=MOCK_SNAPSHOT_PAYLOAD,
    ):
        yield
