"""Common fixtures for the OpenTherm Web tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.opentherm_web.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="OpenTherm",
        domain=DOMAIN,
        data={"host": "example", "secret": "secret"},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opentherm_web.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
