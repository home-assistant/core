"""August tests conftest."""

from unittest.mock import patch

import pytest
from yalexs.manager.ratelimit import _RateLimitChecker


@pytest.fixture(name="mock_discovery", autouse=True)
def mock_discovery_fixture():
    """Mock discovery to avoid loading the whole bluetooth stack."""
    with patch(
        "homeassistant.components.august.data.discovery_flow.async_create_flow"
    ) as mock_discovery:
        yield mock_discovery


@pytest.fixture(name="disable_ratelimit_checks", autouse=True)
def disable_ratelimit_checks_fixture():
    """Disable rate limit checks."""
    with patch.object(_RateLimitChecker, "register_wakeup"):
        yield
