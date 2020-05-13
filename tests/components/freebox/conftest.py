"""Test helpers for Freebox."""
import pytest

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def mock_path():
    """Mock path lib."""
    with patch("homeassistant.components.freebox.router.Path"):
        yield
