"""Common fixtures for the dio_chacon tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from dio_chacon_wifi_api import DIOChaconAPIClient
import pytest

from homeassistant.components.dio_chacon.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_COVER_DEVICE = {
    "L4HActuator_idmock1": {
        "id": "L4HActuator_idmock1",
        "name": "Shutter mock 1",
        "type": "SHUTTER",
        "model": "CERSwd-3B_1.0.6",
        "connected": True,
        "openlevel": 75,
        "movement": "stop",
    }
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.dio_chacon.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock the config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_entry_unique_id",
        data={
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "dummypass",
        },
    )


@pytest.fixture
def mock_dio_chacon_client() -> Generator[AsyncMock]:
    """Mock a Dio Chacon client."""

    client = AsyncMock(spec=DIOChaconAPIClient)
    client.search_all_devices.return_value = MOCK_COVER_DEVICE
    client.move_shutter_direction.return_value = {}
    client.move_shutter_percentage.return_value = {}
    client.disconnect.return_value = {}

    with patch(
        "homeassistant.components.dio_chacon.DIOChaconAPIClient",
        return_value=client,
    ):
        yield client
