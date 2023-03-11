"""Fixtures for Discovergy integration tests."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tests.components.discovergy import GET_METERS


@pytest.fixture
def mock_meters() -> Mock:
    """Patch libraries."""
    with patch("pydiscovergy.Discovergy.get_meters") as discovergy:
        discovergy.side_effect = AsyncMock(return_value=GET_METERS)
        yield discovergy
