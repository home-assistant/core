"""Provide common Atag fixtures."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
async def mock_pyatag_sleep():
    """Mock out pyatag sleeps."""
    with patch("pyatag.gateway.asyncio.sleep"):
        yield
