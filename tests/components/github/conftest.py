"""conftest for the GitHub integration."""
from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.github.const import (
    CONF_ACCESS_TOKEN,
    CONF_REPOSITORIES,
    DEFAULT_REPOSITORIES,
    DOMAIN,
)

from .common import MOCK_ACCESS_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="",
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN},
        options={CONF_REPOSITORIES: DEFAULT_REPOSITORIES},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.github.async_setup_entry", return_value=True):
        yield
