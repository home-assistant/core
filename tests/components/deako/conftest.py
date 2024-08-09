"""deako session fixtures."""

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


@pytest.fixture(name="pydeako_deako_mock", autouse=True)
def pydeako_deako_mock():
    """Mock pydeako deako client."""
    with patch("homeassistant.components.deako.Deako", autospec=True) as mock:
        yield mock


@pytest.fixture(name="pydeako_discoverer_mock", autouse=True)
def pydeako_discoverer_mock(mock_async_zeroconf: MagicMock):
    """Mock pydeako discovery client."""
    with patch("homeassistant.components.deako.DeakoDiscoverer", autospec=True) as mock:
        yield mock
