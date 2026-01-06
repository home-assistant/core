"""Test file for Uhoo config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from uhooapi.errors import UnauthorizedError

from homeassistant import config_entries
from homeassistant.components.uhoo.config_flow import UhooFlowHandler
from homeassistant.components.uhoo.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Mock config
MOCK_CONFIG = {CONF_API_KEY: "test-api-key-123"}
MOCK_CONFIG_DIFFERENT = {CONF_API_KEY: "different-api-key-456"}


@pytest.mark.asyncio
async def test_second_instance_error(
    hass: HomeAssistant,
    bypass_login,
) -> None:
    """Test that errors are shown when trying to add instance with same API key."""

    # First, add one config entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )

    # Verify the first entry was created
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Now try to add another instance with the SAME API key
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )

    # Should abort with "already_configured" since same API key
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_multiple_instances_with_different_keys(
    hass: HomeAssistant,
    bypass_login,
) -> None:
    """Test that multiple instances can be added with different API keys."""

    # Add first instance
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Account 1"
    assert result["data"] == MOCK_CONFIG

    # Add second instance with different API key
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG_DIFFERENT,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Account 2"
    assert result["data"] == MOCK_CONFIG_DIFFERENT


@pytest.mark.asyncio
async def test_form_display(
    hass: HomeAssistant,
) -> None:
    """Test that form is displayed properly when no user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_empty_api_key(
    hass: HomeAssistant,
) -> None:
    """Test that empty API key shows error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_API_KEY: ""},
    )

    # Should return to form with error
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "auth"


@pytest.mark.asyncio
async def test_invalid_api_key(
    hass: HomeAssistant,
) -> None:
    """Test that invalid API key shows error."""
    # Mock the Client to raise UnauthorizedError when login is called
    with patch("homeassistant.components.uhoo.config_flow.Client") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.login = AsyncMock(side_effect=UnauthorizedError("Invalid API key"))
        mock_client_class.return_value = mock_client

        # Also need to mock async_create_clientsession
        with patch(
            "homeassistant.components.uhoo.config_flow.async_create_clientsession"
        ) as mock_create_session:
            mock_create_session.return_value = AsyncMock()

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data=MOCK_CONFIG,
            )

    # Should return to form with error
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "auth"


@pytest.mark.asyncio
async def test_valid_flow(
    hass: HomeAssistant,
    bypass_login,
) -> None:
    """Test successful flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Account 1"
    assert result["data"] == MOCK_CONFIG


@pytest.mark.asyncio
async def test_flow_with_form_interaction(
    hass: HomeAssistant,
    bypass_login,
) -> None:
    """Test flow when user interacts with form (not providing input initially)."""
    # Init flow without data
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Now provide data
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Account 1"
    assert result["data"] == MOCK_CONFIG


# NEW TESTS TO INCREASE COVERAGE:


@pytest.mark.asyncio
async def test_flow_handler_initialization() -> None:
    """Test that UhooFlowHandler initializes correctly."""

    handler = UhooFlowHandler()
    assert handler._errors == {}


@pytest.mark.asyncio
async def test_show_config_form_recursive(
    hass: HomeAssistant,
) -> None:
    """Test the recursive behavior of _show_config_form."""

    handler = UhooFlowHandler()
    handler.hass = hass
    handler._errors = {}

    # Test with None input (should recursively call itself)
    result = await handler._show_config_form(None)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_show_config_form_with_user_input(
    hass: HomeAssistant,
) -> None:
    """Test _show_config_form with user input."""

    handler = UhooFlowHandler()
    handler.hass = hass
    handler._errors = {"base": "auth"}

    # Test with user input
    user_input = {CONF_API_KEY: "test-key"}
    result = await handler._show_config_form(user_input)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "auth"}


@pytest.mark.asyncio
async def test_test_credentials_success(
    hass: HomeAssistant,
) -> None:
    """Test _test_credentials method with successful login."""

    handler = UhooFlowHandler()
    handler.hass = hass

    with patch("homeassistant.components.uhoo.config_flow.Client") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.login = AsyncMock()
        mock_client_class.return_value = mock_client

        # Also need to mock async_create_clientsession
        with patch(
            "homeassistant.components.uhoo.config_flow.async_create_clientsession"
        ) as mock_create_session:
            mock_create_session.return_value = AsyncMock()

            result = await handler._test_credentials("test-api-key")

            assert result is True
            mock_client.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_credentials_unauthorized(
    hass: HomeAssistant,
) -> None:
    """Test _test_credentials method with unauthorized error."""

    handler = UhooFlowHandler()
    handler.hass = hass

    with patch("homeassistant.components.uhoo.config_flow.Client") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.login = AsyncMock(side_effect=UnauthorizedError("Invalid"))
        mock_client_class.return_value = mock_client

        # Also need to mock async_create_clientsession
        with patch(
            "homeassistant.components.uhoo.config_flow.async_create_clientsession"
        ) as mock_create_session:
            mock_create_session.return_value = AsyncMock()

            result = await handler._test_credentials("test-api-key")

            assert result is False
            mock_client.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_credentials_other_exception(
    hass: HomeAssistant,
) -> None:
    """Test _test_credentials method with other exception."""

    handler = UhooFlowHandler()
    handler.hass = hass

    with patch("homeassistant.components.uhoo.config_flow.Client") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.login = AsyncMock(side_effect=Exception("Other error"))
        mock_client_class.return_value = mock_client

        # Also need to mock async_create_clientsession
        with patch(
            "homeassistant.components.uhoo.config_flow.async_create_clientsession"
        ) as mock_create_session:
            mock_create_session.return_value = AsyncMock()

            # Should raise the exception
            with pytest.raises(Exception) as exc_info:
                await handler._test_credentials("test-api-key")

            assert "Other error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_step_user_already_configured(
    hass: HomeAssistant, bypass_login
) -> None:
    """Test async_step_user when entry is already configured."""

    handler = UhooFlowHandler()
    handler.hass = hass

    mock_entry = AsyncMock(spec=ConfigEntry)
    mock_entry.unique_id = "existing-key"
    mock_entry.state = ConfigEntryState.LOADED

    # Mock _async_current_entries to return our mock entry
    handler._async_current_entries = lambda: [mock_entry]

    # Mock async_set_unique_id and _abort_if_unique_id_configured
    with (
        patch.object(handler, "async_set_unique_id"),
        patch.object(handler, "_abort_if_unique_id_configured") as mock_abort,
    ):
        # Make abort method do nothing (simulate not aborting)
        mock_abort.return_value = None

        # Test with same key
        await handler.async_step_user({CONF_API_KEY: "existing-key"})

        # Should call abort check
        mock_abort.assert_called_once()


@pytest.mark.asyncio
async def test_entry_title_numbering_with_existing_entries(
    hass: HomeAssistant,
    bypass_login,
) -> None:
    """Test that entry titles are numbered based on existing entries."""

    # First entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )
    assert result["title"] == "Account 1"

    # Second entry with different key
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG_DIFFERENT,
    )
    assert result["title"] == "Account 2"
