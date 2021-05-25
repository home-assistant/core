"""Fixtures for Seventeentrack methods."""
from unittest.mock import AsyncMock, patch

import py17track
import pytest


@pytest.fixture(autouse=True)
def mock_api():
    """Mock api."""
    with patch.object(py17track.client, "Profile") as mock_profile:
        mock_profile.return_value.login = AsyncMock(return_value=True)
        mock_profile.return_value.packages = AsyncMock(return_value=[])
        mock_profile.return_value.summary = AsyncMock(return_value={})
        yield mock_profile
