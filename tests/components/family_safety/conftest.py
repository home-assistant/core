"""Common fixtures for the Microsoft Family Safety tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.family_safety.coordinator import FamilySafetyCoordinator
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

# Common test data
TEST_USER_ID = "aabbccddee112233"
TEST_REFRESH_TOKEN = "refresh-token-here"
TEST_FIRST_NAME = "John"
TEST_SURNAME = "Doe"
TEST_KEY = "example_key"
TEST_ACCOUNT_NAME = f"{TEST_FIRST_NAME} {TEST_SURNAME}"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.family_safety.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_authenticator_client() -> Generator[MagicMock]:
    """Mock the Family Safety Authenticator class and its awaitable 'create' method."""
    mock_auth_instance = AsyncMock()
    mock_auth_instance.perform_login.return_value = True
    mock_auth_instance.perform_refresh.return_value = True

    type(mock_auth_instance).user_id = PropertyMock(return_value=TEST_USER_ID)
    type(mock_auth_instance).refresh_token = PropertyMock(
        return_value=TEST_REFRESH_TOKEN
    )

    mock_http_response = AsyncMock()
    mock_http_response.status = 200
    mock_http_response.json.return_value = {}
    mock_request_method = AsyncMock()
    mock_request_method.__aenter__.return_value = mock_http_response
    mock_request_method.__aexit__.return_value = None
    mock_auth_instance.client_session = MagicMock()
    mock_auth_instance.client_session.request = mock_request_method

    with (
        # Patch the Authenticator.create class method in homeassistant's component.
        patch(
            "homeassistant.components.family_safety.Authenticator.create",
            new_callable=AsyncMock,
            return_value=mock_auth_instance,
        ),
        # Patch the Authenticator class itself in homeassistant's component.
        patch(
            "homeassistant.components.family_safety.Authenticator",
            new=mock_auth_instance,
        ),
        # Patch the Authenticator in the config_flow module.
        patch(
            "homeassistant.components.family_safety.config_flow.Authenticator",
            new=mock_auth_instance,
        ),
        # *** PATCHES FOR UNDERLYING LIBRARY ***
        # Patch the Authenticator class in the pyfamilysafety library.
        patch(
            "pyfamilysafety.Authenticator",
            new=mock_auth_instance,
        ),
        # Patch the Authenticator.create class method in the pyfamilysafety library.
        patch(
            "pyfamilysafety.Authenticator.create",
            new_callable=AsyncMock,
            return_value=mock_auth_instance,
        ),
    ):
        yield mock_auth_instance


@pytest.fixture
def mock_coordinator() -> AsyncMock:
    """Fixture for a mocked FamilySafetyCoordinator."""
    coordinator = AsyncMock(spec=FamilySafetyCoordinator)
    # If the coordinator has a hass attribute, mock it.
    coordinator.hass = AsyncMock()
    return coordinator


# --- Mocks for external dependencies ---


class MockAccount:
    """A simple mock for the pyfamilysafety.Account class with necessary attributes for sensors."""

    def __init__(
        self,
        user_id,
        first_name,
        surname,
        today_screentime_usage=0,
        account_balance=0.0,
        account_currency="USD",
    ) -> None:
        """Create MockAccount."""
        self.user_id = user_id
        self.first_name = first_name
        self.surname = surname
        self.today_screentime_usage = today_screentime_usage
        self.account_balance = account_balance
        self.account_currency = account_currency
        self.add_account_callback = MagicMock()
        self.remove_account_callback = MagicMock()


@pytest.fixture
def mock_account() -> MockAccount:
    """Fixture for a mocked Account instance."""
    return MockAccount(TEST_USER_ID, TEST_FIRST_NAME, TEST_SURNAME)


@pytest.fixture
def mock_coordinator_with_api() -> AsyncMock:
    """Fixture for a mocked FamilySafetyCoordinator including a mocked API."""
    coordinator = AsyncMock(spec=FamilySafetyCoordinator)
    coordinator.hass = AsyncMock()  # Mock the hass attribute if accessed

    # Mock the api attribute and its methods/properties
    coordinator.api = MagicMock()
    coordinator.api.accounts = []  # This will be populated by tests as needed
    coordinator.api.get_account_requests = MagicMock(
        return_value=[]
    )  # Default empty list

    return coordinator


@pytest.fixture
def mock_account_data() -> MockAccount:
    """Fixture for a mocked Account instance with specific data."""
    return MockAccount(
        user_id="test_user_001",
        first_name="Test",
        surname="User",
        today_screentime_usage=120 * 60 * 1000,  # 120 minutes in milliseconds
        account_balance=25.50,
        account_currency="USD",
    )


@pytest.fixture
def mock_add_entities() -> AddConfigEntryEntitiesCallback:
    """Fixture for a mocked AddConfigEntryEntitiesCallback."""
    return AsyncMock(spec=AddConfigEntryEntitiesCallback)
