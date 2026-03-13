"""Common fixtures for the Amcrest tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.amcrest import PLATFORMS
from homeassistant.components.amcrest.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.100"
TEST_PORT = 80
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"
TEST_SERIAL = "12345"
TEST_NAME = "Amcrest Camera"


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.amcrest.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_NAME,
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_NAME: TEST_NAME,
        },
        unique_id=TEST_SERIAL,
    )


@pytest.fixture
def mock_amcrest_api() -> Generator[MagicMock]:
    """Return a mocked AmcrestChecker."""
    with patch(
        "homeassistant.components.amcrest.config_flow.AmcrestChecker",
    ) as mock_api_class:
        api = MagicMock()

        async def _async_current_time():
            return None

        async def _async_serial_number():
            return TEST_SERIAL

        # Use property-like behavior: attribute returns a coroutine when accessed
        api.async_current_time = _async_current_time()
        api.async_serial_number = _async_serial_number()
        mock_api_class.return_value = api
        yield mock_api_class


@pytest.fixture(autouse=True)
async def mock_patch_platforms() -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", PLATFORMS):
        yield
