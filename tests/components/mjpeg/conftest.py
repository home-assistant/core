"""Fixtures for MJPEG IP Camera integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from requests_mock import Mocker

from homeassistant.components.mjpeg.const import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My MJPEG Camera",
        domain=DOMAIN,
        data={},
        options={
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_MJPEG_URL: "https://example.com/mjpeg",
            CONF_PASSWORD: "supersecret",
            CONF_STILL_IMAGE_URL: "http://example.com/still",
            CONF_USERNAME: "frenck",
            CONF_VERIFY_SSL: True,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mjpeg.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_reload_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.mjpeg.async_reload_entry") as mock_reload:
        yield mock_reload


@pytest.fixture
def mock_mjpeg_requests(requests_mock: Mocker) -> Generator[Mocker, None, None]:
    """Fixture to provide a requests mocker."""
    requests_mock.get("https://example.com/mjpeg", text="resp")
    requests_mock.get("https://example.com/still", text="resp")
    yield requests_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_mjpeg_requests: Mocker
) -> MockConfigEntry:
    """Set up the MJPEG IP Camera integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
