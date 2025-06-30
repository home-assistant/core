from typing import Any, Coroutine
from unittest.mock import AsyncMock
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from frisquet_connect.const import DOMAIN
from frisquet_connect.devices.frisquet_connect_coordinator import (
    FrisquetConnectCoordinator,
)
from frisquet_connect.devices.frisquet_connect_device import (
    FrisquetConnectDevice,
)
from utils import mock_endpoints, read_json_file_as_json


@pytest.fixture
def mock_add_entities():
    return AsyncMock(spec=AddEntitiesCallback)


@pytest.fixture
def mock_hass():
    mock = AsyncMock(spec=HomeAssistant)
    mock.data = {}
    return mock


@pytest.fixture
def mock_entry():
    mock_entry_file = read_json_file_as_json("mock_entry")
    mock = AsyncMock(spec=ConfigEntry)
    mock.data = mock_entry_file.get("data")
    mock.unique_id = mock_entry_file.get("unique_id")

    # For debug purpose with real data
    # dotenv.load_dotenv()

    # Use environment variables if available to override the mock data
    # if os.getenv("EMAIL") and os.getenv("PASSWORD") and os.getenv("SITE_ID"):
    #     mock.data["email"] = os.getenv("EMAIL")
    #     mock.data["password"] = os.getenv("PASSWORD")
    #     mock.data["site_id"] = os.getenv("SITE_ID")

    return mock


async def async_core_setup_entry_with_site_id_mutated(
    async_setup_entry: Coroutine[Any, Any, None],
    mock_add_entities: AddEntitiesCallback = None,
    hass: HomeAssistant = None,
    entry: ConfigEntry = None,
    site_id: str = None,
):
    # Initialize the mocks
    mock_endpoints()
    entry.data = {"site_id": site_id}

    service = FrisquetConnectDevice(entry.data.get("email"), entry.data.get("password"))
    coordinator = FrisquetConnectCoordinator(hass, service, entry.data.get("site_id"))
    await coordinator._async_refresh()
    hass.data[DOMAIN] = {entry.unique_id: coordinator}

    if mock_add_entities:
        # Test the feature
        await async_setup_entry(hass, entry, mock_add_entities)

        # Assertions
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 0
    else:
        await async_setup_entry(hass, entry)
