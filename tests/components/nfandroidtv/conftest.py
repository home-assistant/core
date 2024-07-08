"""Conftest for nfandroidtv."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
async def create_mocked_tv():
    """Create mocked tv."""
    mocked_tv = AsyncMock()
    mocked_tv.get_state = AsyncMock()
    return mocked_tv
