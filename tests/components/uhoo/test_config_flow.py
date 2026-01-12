"""Test the Uhoo config flow."""

from aiohttp.client_exceptions import ClientConnectorDNSError
from uhooapi.errors import UnauthorizedError

from homeassistant.components.uhoo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_happy_flow(
    hass: HomeAssistant, mock_uhoo_client, mock_setup_entry
) -> None:
    """Test a complete user flow from start to finish with errors and success."""
    # Step 1: Initialize the flow ONCE and get the flow_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    flow_id = result["flow_id"]

    # Step 2: Test submitting an empty API key within the SAME flow
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_API_KEY: ""},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
    mock_uhoo_client.login.assert_not_called()

    # Step 3: Test submitting an invalid API key within the SAME flow
    mock_uhoo_client.login.side_effect = UnauthorizedError("Invalid credentials")
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_API_KEY: "invalid-api-key"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}
    mock_uhoo_client.login.assert_called_once()

    # Step 4: Reset mock and test successful submission within the SAME flow
    mock_uhoo_client.login.reset_mock()
    mock_uhoo_client.login.side_effect = None
    mock_uhoo_client.login.return_value = None

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        user_input={CONF_API_KEY: "valid-api-key-12345"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "uHoo (12345)"
    assert result["data"] == {CONF_API_KEY: "valid-api-key-12345"}

    # Verify the setup was called
    await hass.async_block_till_done()
    mock_setup_entry.assert_called_once()


async def test_form_duplicate_entry(
    hass: HomeAssistant, mock_uhoo_client, mock_uhoo_config_entry
) -> None:
    """Test duplicate entry aborts."""
    mock_uhoo_client.login.return_value = None
    mock_uhoo_config_entry.add_to_hass(hass)

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


async def test_form_client_exception(hass: HomeAssistant, mock_uhoo_client) -> None:
    """Test form when client raises an expected exception."""
    # Use a ConnectionError which is caught by your config flow
    mock_uhoo_client.login.side_effect = [ConnectionError("Cannot connect"), None]

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
    mock_uhoo_client.login.assert_called_once()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "api-key"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_connection_error(hass: HomeAssistant, mock_uhoo_client) -> None:
    """Test DNS connection error during login."""
    # Create a ClientConnectorDNSError
    mock_uhoo_client.login.side_effect = [
        ClientConnectorDNSError(
            ConnectionError("Cannot connect"), OSError("DNS failure")
        ),
        None,  # Second call succeeds
    ]

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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "api-key"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_setup_entry,
) -> None:
    """Test the full user flow from start to finish."""
    # Mock successful login
    mock_uhoo_client.login.return_value = None

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


async def test_complete_integration_flow(
    hass: HomeAssistant,
    mock_uhoo_client,
    mock_setup_entry,
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
    mock_uhoo_client.login.side_effect = UnauthorizedError("Invalid")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "wrong-key"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Step 3: User corrects and enters valid API key
    mock_uhoo_client.login.side_effect = None
    mock_uhoo_client.login.return_value = None
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
