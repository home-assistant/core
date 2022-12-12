"""Utilities for Risco tests."""
from unittest.mock import AsyncMock, MagicMock

TEST_SITE_UUID = "test-site-uuid"
TEST_SITE_NAME = "test-site-name"


def zone_mock():
    """Return a mocked zone."""
    return MagicMock(
        triggered=False, bypassed=False, bypass=AsyncMock(return_value=True)
    )
