"""Fixtures for Seventeentrack methods."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
import seventeentrack


@pytest.fixture(autouse=True)
def mock_api():
    """Mock api."""
    with patch.object(
        seventeentrack.client,
        "Profile",
        return_value=Mock(account_id="email@email.com"),
    ) as mock_profile:
        mock_profile.return_value.login = AsyncMock(return_value=True)
        mock_profile.return_value.packages = AsyncMock(return_value=[])
        mock_profile.return_value.summary = AsyncMock(return_value={})
        mock_profile.return_value.add_package_with_carrier = AsyncMock()
        yield mock_profile
