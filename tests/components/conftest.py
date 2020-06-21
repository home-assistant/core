"""Fixtures for component testing."""
import pytest

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def prevent_io():
    """Fixture to prevent certain I/O from happening."""
    with patch(
        "homeassistant.components.http.ban.async_load_ip_bans_config", return_value=[],
    ):
        yield
