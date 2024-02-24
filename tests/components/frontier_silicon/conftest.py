"""Configuration for frontier_silicon tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.frontier_silicon.const import CONF_WEBFSAPI_URL, DOMAIN
from homeassistant.const import CONF_PIN

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock Frontier Silicon config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock_radio_id",
        data={CONF_WEBFSAPI_URL: "http://1.1.1.1:80/webfsapi", CONF_PIN: "1234"},
    )


@pytest.fixture(autouse=True)
def mock_valid_device_url() -> Generator[None, None, None]:
    """Return a valid webfsapi endpoint."""
    with patch(
        "afsapi.AFSAPI.get_webfsapi_endpoint",
        return_value="http://1.1.1.1:80/webfsapi",
    ):
        yield


@pytest.fixture(autouse=True)
def mock_valid_pin() -> Generator[None, None, None]:
    """Make get_friendly_name return a value, indicating a valid pin."""
    with patch(
        "afsapi.AFSAPI.get_friendly_name",
        return_value="Name of the device",
    ):
        yield


@pytest.fixture(autouse=True)
def mock_radio_id() -> Generator[None, None, None]:
    """Return a valid radio_id."""
    with patch("afsapi.AFSAPI.get_radio_id", return_value="mock_radio_id"):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.frontier_silicon.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
