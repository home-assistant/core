"""Fixtures for tests."""

from collections.abc import Generator
from itertools import cycle
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mydevolo() -> Generator[None]:
    """Fixture to patch mydevolo into a desired state."""
    mydevolo = MagicMock()
    mydevolo.uuid.return_value = "123456"
    mydevolo.credentials_valid.return_value = True
    mydevolo.maintenance.return_value = False
    mydevolo.get_gateway_ids.return_value = ["1400000000000001", "1400000000000002"]
    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo",
        side_effect=cycle([mydevolo]),
    ):
        yield mydevolo


@pytest.fixture(autouse=True)
def devolo_home_control_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""
