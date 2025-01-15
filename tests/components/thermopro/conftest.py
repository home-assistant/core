"""ThermoPro session fixtures."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_bluetooth_adverts(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Allow mocking returned bt adverts."""
    mock = AsyncMock(side_effect=TimeoutError())

    monkeypatch.setattr(
        "homeassistant.components.thermopro.button.async_process_advertisements",
        mock,
    )

    return mock
