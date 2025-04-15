"""Define test fixtures for Obihai."""

from collections.abc import Generator
from socket import gaierror
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""

    with patch(
        "homeassistant.components.obihai.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_gaierror() -> Generator[AsyncMock]:
    """Override async_setup_entry."""

    with patch(
        "homeassistant.components.obihai.config_flow.gethostbyname",
        side_effect=gaierror(),
    ) as mock_setup_entry:
        yield mock_setup_entry
