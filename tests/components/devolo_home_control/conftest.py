"""Fixtures for tests."""

from collections.abc import Generator
from itertools import cycle
from unittest.mock import MagicMock, patch

import pytest

from .mocks import MydevoloMock


@pytest.fixture(autouse=True)
def mydevolo() -> Generator[None]:
    """Fixture to patch mydevolo into a desired state."""
    mydevolo = MydevoloMock()
    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo",
        side_effect=cycle([mydevolo]),
    ):
        yield mydevolo


@pytest.fixture(autouse=True)
def devolo_home_control_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""
