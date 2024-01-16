"""Common fixtures for the Ecovacs tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ecovacs.async_setup_entry", return_value=True
    ) as async_setup_entry:
        yield async_setup_entry
