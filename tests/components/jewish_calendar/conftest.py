"""Common fixtures for the jewish_calendar tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.jewish_calendar import config_flow

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=config_flow.DEFAULT_NAME,
        domain=config_flow.DOMAIN,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.jewish_calendar.async_setup_entry", return_value=True
    ):
        yield
