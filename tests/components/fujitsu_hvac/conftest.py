"""Common fixtures for the Fujitsu HVAC (based on Ayla IOT) tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fujitsu_hvac.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
