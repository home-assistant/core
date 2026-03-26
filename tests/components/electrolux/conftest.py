"""Common fixtures for the electrolux tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from electrolux_group_developer_sdk.client.appliance_data_factory import (
    appliance_data_factory,
)
from electrolux_group_developer_sdk.client.dto.appliance_state import ApplianceState
import pytest

from homeassistant.components.electrolux.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import (
    APPLIANCE_FIXTURES,
    get_fixture_name,
    load_appliance,
    load_appliance_details,
    load_appliance_state,
    setup_integration,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.electrolux.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up Electrolux integration for tests."""
    await setup_integration(hass, mock_config_entry)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Electrolux",
        unique_id="mock_user_id",
        data={
            CONF_API_KEY: "mock_api_key",
            CONF_ACCESS_TOKEN: "mock_access_token",
            CONF_REFRESH_TOKEN: "mock_refresh_token",
        },
    )


@pytest.fixture
def mock_appliance_client() -> Generator[AsyncMock]:
    """Mock the Electrolux Group Developer SDK client."""
    with (
        patch(
            "homeassistant.components.electrolux.ApplianceClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.electrolux.config_flow.ApplianceClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value

        def get_appliance_state(appliance_id: str) -> ApplianceState | None:
            return load_appliance_state(get_fixture_name(appliance_id))

        client.get_appliance_state.side_effect = get_appliance_state

        yield client


@pytest.fixture
def mock_token_manager() -> Generator[AsyncMock]:
    """Mock the Electrolux Group Developer SDK token manager."""
    with (
        patch(
            "homeassistant.components.electrolux.TokenManager",
            autospec=True,
        ) as mock_token_manager,
        patch(
            "homeassistant.components.electrolux.config_flow.TokenManager",
            new=mock_token_manager,
        ),
    ):
        token_manager = mock_token_manager.return_value

        token_manager.ensure_credentials.return_value = None
        token_manager.get_user_id.return_value = "mock_user_id"

        yield token_manager


@pytest.fixture
def appliance_fixture() -> str | None:
    """Return the appliance fixture that should be loaded, or None if all appliances should be loaded."""
    return None


@pytest.fixture
def appliances(
    mock_appliance_client: AsyncMock, appliance_fixture: str | None
) -> AsyncMock:
    """Mock the list of appliances."""
    appliance_names = []
    if appliance_fixture is not None:
        appliance_names.append(appliance_fixture)
    else:
        appliance_names.extend(APPLIANCE_FIXTURES)

    appliance_data_list = []
    for appliance_name in appliance_names:
        appliance = load_appliance(appliance_name)
        details = load_appliance_details(appliance_name)
        state = load_appliance_state(appliance_name)

        appliance_data = appliance_data_factory(
            appliance=appliance,
            details=details,
            state=state,
        )

        appliance_data_list.append(appliance_data)

    mock_appliance_client.get_appliance_data.return_value = appliance_data_list

    return mock_appliance_client
