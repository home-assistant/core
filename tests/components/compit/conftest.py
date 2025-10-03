"""Common fixtures for the Compit tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.compit.const import DOMAIN
from homeassistant.const import CONF_EMAIL

from .consts import CONFIG_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_INPUT,
        unique_id=CONFIG_INPUT[CONF_EMAIL],
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.compit.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_compit_api() -> Generator[AsyncMock]:
    """Mock CompitApiConnector."""
    with patch(
        "homeassistant.components.compit.config_flow.CompitApiConnector.init",
    ) as mock_api:
        yield mock_api
