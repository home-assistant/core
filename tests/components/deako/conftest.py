"""deako session fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.deako.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
    )


@pytest.fixture(autouse=True)
def pydeako_deako_mock() -> Generator[MagicMock]:
    """Mock pydeako deako client."""
    with patch("homeassistant.components.deako.Deako", autospec=True) as mock:
        yield mock


@pytest.fixture(autouse=True)
def pydeako_discoverer_mock(mock_async_zeroconf: MagicMock) -> Generator[MagicMock]:
    """Mock pydeako discovery client."""
    with (
        patch("homeassistant.components.deako.DeakoDiscoverer", autospec=True) as mock,
        patch("homeassistant.components.deako.config_flow.DeakoDiscoverer", new=mock),
    ):
        yield mock


@pytest.fixture
def mock_deako_setup() -> Generator[MagicMock]:
    """Mock async_setup_entry for config flow tests."""
    with patch(
        "homeassistant.components.deako.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
