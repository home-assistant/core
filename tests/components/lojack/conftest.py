"""Test fixtures for the LoJack integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from lojack_api import LoJackClient
from lojack_api.device import Vehicle
from lojack_api.models import Location
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
    TEST_USER_ID,
    TEST_USERNAME,
    TEST_VIN,
    TEST_YEAR,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USER_ID,
        data={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        title=f"LoJack ({TEST_USERNAME})",
    )


@pytest.fixture
def mock_location() -> Location:
    """Return a mock LoJack location."""
    return Location(
        latitude=TEST_LATITUDE,
        longitude=TEST_LONGITUDE,
        accuracy=TEST_ACCURACY,
        heading=TEST_HEADING,
        address=TEST_ADDRESS,
        timestamp=TEST_TIMESTAMP,
    )


@pytest.fixture
def mock_device(mock_location: Location) -> MagicMock:
    """Return a mock LoJack device."""
    device = create_autospec(Vehicle, instance=True)
    device.id = TEST_DEVICE_ID
    device.name = TEST_DEVICE_NAME
    device.vin = TEST_VIN
    device.make = TEST_MAKE
    device.model = TEST_MODEL
    device.year = TEST_YEAR
    device.get_location = AsyncMock(return_value=mock_location)
    return device


@pytest.fixture
def mock_lojack_client(
    mock_device: MagicMock,
) -> Generator[MagicMock]:
    """Return a mock LoJack client."""
    client = create_autospec(LoJackClient, instance=True)
    client.user_id = TEST_USER_ID
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
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
