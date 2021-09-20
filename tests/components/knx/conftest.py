"""conftest for knx."""

from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture(autouse=True)
def knx_ip_interface_mock():
    """Create a knx ip interface mock."""
    mock = Mock()
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.send_telegram = AsyncMock()
    return mock
