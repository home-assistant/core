"""Common fixtures for the TRMNL tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from trmnl.models import DevicesResponse, UserResponse

from homeassistant.components.trmnl.const import DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.trmnl.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test",
        unique_id="30561",
        data={CONF_API_KEY: "user_aaaaaaaaaa"},
    )


@pytest.fixture
def mock_trmnl_client() -> Generator[AsyncMock]:
    """Mock TRMNL client."""
    with (
        patch(
            "homeassistant.components.trmnl.coordinator.TRMNLClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.trmnl.config_flow.TRMNLClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_me.return_value = UserResponse.from_json(
            load_fixture("me.json", DOMAIN)
        ).data
        client.get_devices.return_value = DevicesResponse.from_json(
            load_fixture("devices.json", DOMAIN)
        ).data
        yield client
