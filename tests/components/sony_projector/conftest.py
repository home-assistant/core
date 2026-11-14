"""Common fixtures for the Sony Projector tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sony_projector.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST

TEST_HOST = "192.0.2.10"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sony_projector.async_setup_entry",
        return_value=None,
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_projector() -> Generator[MagicMock]:
    """Mock the pySDCP projector, which reports it is on."""
    with patch("pysdcp.Projector") as projector_class:
        projector = projector_class.return_value
        projector.get_power.return_value = True
        projector.set_power.return_value = True
        yield projector


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_HOST: TEST_HOST},
        entry_id="01JSONYPROJECTOR0000000000",
    )
