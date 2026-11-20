"""Common fixtures for the iperf3 tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from . import make_result


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the iperf3 client."""
    with patch("homeassistant.components.iperf3.iperf3.Client") as client_cls:
        client_cls.return_value.run.return_value = make_result()
        yield client_cls.return_value
