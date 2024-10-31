"""Configure tests for the Onkyo integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.onkyo.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.onkyo.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create Onkyo entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Onkyo",
        data={},
    )
