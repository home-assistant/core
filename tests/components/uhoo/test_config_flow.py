"""Test the Uhoo config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp.client_exceptions import ClientConnectorDNSError
import pytest
from uhooapi.errors import UnauthorizedError

from homeassistant import config_entries
from homeassistant.components.uhoo.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Constants for source types
SOURCE_USER = config_entries.SOURCE_USER


@pytest.fixture(autouse=True)
def mock_client():
    """Mock the Uhoo client."""
    with patch("homeassistant.components.uhoo.config_flow.Client") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.login = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture(autouse=True)
def mock_async_create_clientsession():
    """Mock async_create_clientsession."""
    with patch(
        "homeassistant.components.uhoo.config_flow.async_create_clientsession"
    ) as mock_session:
        mock_session.return_value = AsyncMock()
        yield mock_session


@pytest.fixture
def mock_setup_entry():
    """Mock the setup entry."""
    with patch(
        "homeassistant.components.uhoo.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


class TestUhooFlowHandler:
    """Test the Uhoo config flow."""

    async def test_show_config_form(self, hass: HomeAssistant):
        """Test the initial form is shown."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_form_with_empty_api_key(self, hass: HomeAssistant, mock_client):
        """Test form with empty API key shows error."""
        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # Submit empty API key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: ""},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}
        mock_client.login.assert_not_called()

    async def test_form_invalid_credentials(self, hass: HomeAssistant, mock_client):
        """Test form with invalid credentials shows error."""
        mock_client.login.side_effect = UnauthorizedError("Invalid credentials")

        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # Submit invalid API key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "invalid-api-key"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}
        mock_client.login.assert_called_once()

    async def test_form_valid_credentials(self, hass: HomeAssistant, mock_client):
        """Test form with valid credentials creates entry."""
        mock_client.login.return_value = None

        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # Submit valid API key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "valid-api-key-12345"},
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Check title format matches your implementation
        assert result["title"] == "uHoo (12345)"  # Last 5 chars of the key
        assert result["data"] == {CONF_API_KEY: "valid-api-key-12345"}
        mock_client.login.assert_called_once()

    async def test_form_duplicate_entry(self, hass: HomeAssistant, mock_client):
        """Test duplicate entry aborts."""
        mock_client.login.return_value = None

        # Create first entry using MockConfigEntry
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="valid-api-key-12345",
            data={CONF_API_KEY: "valid-api-key-12345"},
            title="uHoo (12345)",
        )
        entry.add_to_hass(hass)

        # Try to create duplicate
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "valid-api-key-12345"},  # Same API key
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    async def test_form_client_exception(self, hass: HomeAssistant, mock_client):
        """Test form when client raises an expected exception."""
        # Use a ConnectionError which is caught by your config flow
        mock_client.login.side_effect = ConnectionError("Cannot connect")

        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # Submit API key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api-key"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}
        mock_client.login.assert_called_once()

    async def test_connection_error(self, hass: HomeAssistant, mock_client):
        """Test DNS connection error during login."""
        # Create a ClientConnectorDNSError
        mock_client.login.side_effect = ClientConnectorDNSError(
            ConnectionError("Cannot connect"), OSError("DNS failure")
        )

        # Start the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # Submit API key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "api-key"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_full_user_flow(
        self,
        hass: HomeAssistant,
        mock_client: AsyncMock,
        mock_setup_entry: AsyncMock,
    ) -> None:
        """Test the full user flow from start to finish."""
        # Mock successful login
        mock_client.login.return_value = None

        # Step 1: Initialize the flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        # Step 2: Submit valid credentials
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "valid-api-key-test12345"},
        )

        # Step 3: Verify entry creation
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "uHoo (12345)"  # Last 5 chars
        assert result["data"] == {CONF_API_KEY: "valid-api-key-test12345"}
        assert result["result"]

        # Verify setup was called
        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()

    async def test_flow_cancellation(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test user flow cancellation."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        # The flow should still be in form state
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"


# Integration test for the full flow
async def test_complete_integration_flow(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test complete integration flow from user perspective."""
    # Step 1: User starts the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Step 2: User enters invalid API key
    mock_client.login.side_effect = UnauthorizedError("Invalid")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "wrong-key"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Step 3: User corrects and enters valid API key
    mock_client.login.side_effect = None
    mock_client.login.return_value = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "correct-key-67890"},
    )

    # Step 4: Verify successful entry creation
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "correct-key-67890"}
    assert result["title"] == "uHoo (67890)"  # Last 5 chars

    # Verify the entry was added to hass
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_API_KEY] == "correct-key-67890"
    assert entries[0].unique_id == "correct-key-67890"

    await hass.async_block_till_done()
    mock_setup_entry.assert_called_once()
