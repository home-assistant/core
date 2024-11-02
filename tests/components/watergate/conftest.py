"""Fixtures for watergate platform tests."""

from collections.abc import Generator

import pytest

from homeassistant.components.watergate.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME

from . import DEFAULT_DEVICE_STATE
from .const import MOCK_CONFIG, MOCK_WEBHOOK_ID

from tests.common import AsyncMock, MockConfigEntry, patch


@pytest.fixture
def mock_watergate_client() -> Generator[AsyncMock]:
    """Fixture to mock WatergateLocalApiClient."""
    with (
        patch(
            "homeassistant.components.watergate.WatergateLocalApiClient"
        ) as mock_client_main,
        patch(
            "homeassistant.components.watergate.config_flow.WatergateLocalApiClient",
            new=mock_client_main,
        ),
    ):
        mock_client_instance = mock_client_main.return_value

        mock_client_instance.async_set_webhook_url = AsyncMock(return_value=None)
        mock_client_instance.async_set_valve_state = AsyncMock(return_value=None)
        mock_client_instance.async_get_device_state = AsyncMock(
            return_value=DEFAULT_DEVICE_STATE
        )
        yield mock_client_instance


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.watergate.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_webhook_id_generatio() -> Generator[None]:
    """Fixture to mock webhook_id generation."""
    with patch(
        "homeassistant.components.watergate.config_flow.webhook_generate_id",
        return_value=MOCK_WEBHOOK_ID,
    ):
        yield


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Create full mocked entry to be used in config_flow tests."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Existing Device",
        data=MOCK_CONFIG,
        source="user",
        entry_id="12345",
    )


@pytest.fixture
def user_input() -> dict[str, str]:
    """Create user input for config_flow tests."""
    return {
        CONF_NAME: "Test Device",
        CONF_IP_ADDRESS: "192.168.1.100",
    }
