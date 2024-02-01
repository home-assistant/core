"""Common fixtures for the World Air Quality Index (WAQI) tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.waqi.const import CONF_STATION_NUMBER, DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.waqi.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="4584",
        title="de Jongweg, Utrecht",
        data={CONF_API_KEY: "asd", CONF_STATION_NUMBER: 4584},
    )
