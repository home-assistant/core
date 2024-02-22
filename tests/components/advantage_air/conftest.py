"""Fixtures for advantage_air."""
from __future__ import annotations

import pytest

from . import patch_get, patch_update


@pytest.fixture
def mock_get():
    """Fixture to patch the Advantage Air async_get method."""
    with patch_get() as mock_get:
        yield mock_get


@pytest.fixture
def mock_update():
    """Fixture to patch the Advantage Air async_get method."""
    with patch_update() as mock_get:
        yield mock_get
