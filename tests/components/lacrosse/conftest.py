"""Fixtures for LaCrosse integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent config entry setup during config flow tests."""
    with patch(
        "homeassistant.components.lacrosse.async_setup_entry", return_value=True
    ) as mock:
        yield mock


@pytest.fixture
def mock_lacrosse() -> Generator[None]:
    """Prevent config-flow tests from opening a serial receiver."""
    with patch("homeassistant.components.lacrosse.config_flow.pylacrosse.LaCrosse"):
        yield
