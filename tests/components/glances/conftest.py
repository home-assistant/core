"""Conftest for speedtestdotnet."""
from unittest.mock import AsyncMock, patch

import pytest

from . import MOCK_DATA


@pytest.fixture(autouse=True)
def mock_api():
    """Mock glances api."""
    with patch("homeassistant.components.glances.Glances") as mock_api:
        mock_api.return_value.get_data = AsyncMock(return_value=None)
        mock_api.return_value.data.return_value = MOCK_DATA
        yield mock_api
