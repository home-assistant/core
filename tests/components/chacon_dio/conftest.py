"""Common fixtures for the chacon_dio tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.chacon_dio.const import DOMAIN
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
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.chacon_dio.async_setup_entry", return_value=True
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

    with (
        patch(
            "homeassistant.components.chacon_dio.DIOChaconAPIClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.chacon_dio.config_flow.DIOChaconAPIClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        # Default values for the tests using this mock :
        client.get_user_id.return_value = "dummy-user-id"
        client.search_all_devices.return_value = MOCK_COVER_DEVICE

        client.switch_switch.return_value = {}

        client.move_shutter_direction.return_value = {}
        client.disconnect.return_value = {}

        yield client
