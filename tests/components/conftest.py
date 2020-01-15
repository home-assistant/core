"""Fixtures for component testing."""
from unittest.mock import patch

import pytest

from tests.common import mock_coro


@pytest.fixture(autouse=True)
def prevent_io():
    """Fixture to prevent certain I/O from happening."""
    with patch(
        "homeassistant.components.http.ban.async_load_ip_bans_config",
        side_effect=lambda *args: mock_coro([]),
    ):
        yield
