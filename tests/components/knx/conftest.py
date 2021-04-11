"""conftest for knx."""

from typing import List
from unittest.mock import AsyncMock, Mock

import pytest


class KNXIPMock(Mock):
    """Class for mocked KNX IP class."""

    def assert_telegrams_gas(self, gas: List[str], msg: str):
        """Assert telegram count and group addresses."""
        assert self.send_telegram.call_count == len(
            gas
        ), f"Expected telegram count mismatch for {msg}"
        for idx in range(0, len(gas)):
            assert (
                str(self.send_telegram.mock_calls[idx][1][0].destination_address)
                == gas[idx]
            ), f"Expected telegram address mismatch for {msg}"


@pytest.fixture(autouse=True)
def knx_ip_interface_mock():
    """Create a knx ip interface mock."""
    mock = KNXIPMock()
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.send_telegram = AsyncMock()
    return mock
