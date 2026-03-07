"""Test fixtures for the LoJack integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.lojack.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (
    TEST_ACCURACY,
    TEST_ADDRESS,
    TEST_DEVICE_ID,
    TEST_DEVICE_NAME,
    TEST_HEADING,
    TEST_LATITUDE,
    TEST_LONGITUDE,
    TEST_MAKE,
    TEST_MODEL,
    TEST_PASSWORD,
    TEST_TIMESTAMP,
    TEST_USERNAME,
    TEST_VIN,
    TEST_YEAR,
)

from tests.common import MockConfigEntry


class MockAuthenticationError(Exception):
    """Mock AuthenticationError from lojack_api."""


class MockApiError(Exception):
    """Mock ApiError from lojack_api."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        title=f"LoJack ({TEST_USERNAME})",
    )


@pytest.fixture
def mock_device() -> MagicMock:
    """Return a mock LoJack device."""
    device = MagicMock()
    device.id = TEST_DEVICE_ID
    device.name = TEST_DEVICE_NAME
    device.vin = TEST_VIN
    device.make = TEST_MAKE
    device.model = TEST_MODEL
    device.year = TEST_YEAR
    return device


@pytest.fixture
def mock_location() -> MagicMock:
    """Return a mock LoJack location."""
    location = MagicMock()
    location.latitude = TEST_LATITUDE
    location.longitude = TEST_LONGITUDE
    location.accuracy = TEST_ACCURACY
    location.heading = TEST_HEADING
    location.address = TEST_ADDRESS
    location.timestamp = TEST_TIMESTAMP
    return location


@pytest.fixture
def mock_lojack_client(
    mock_device: MagicMock, mock_location: MagicMock
) -> Generator[AsyncMock]:
    """Return a mock LoJack client."""
    mock_device.get_location = AsyncMock(return_value=mock_location)

    client = AsyncMock()
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.LoJackClient.create",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.lojack.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_authentication_error() -> type[Exception]:
    """Return mock AuthenticationError class."""
    return MockAuthenticationError


@pytest.fixture
def mock_api_error() -> type[Exception]:
    """Return mock ApiError class."""
    return MockApiError
