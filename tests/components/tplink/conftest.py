"""tplink conftest."""

import pytest

from . import _patch_discovery


@pytest.fixture
def mock_discovery():
    """Mock python-kasa discovery."""
    with _patch_discovery() as mock_discover:
        mock_discover.return_value = {}
        yield mock_discover
