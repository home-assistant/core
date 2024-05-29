"""Standard fixtures for the Fjäråskupan integration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""
