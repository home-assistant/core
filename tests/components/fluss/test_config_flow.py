"""Test Script for Config_Flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from fluss_api import FlussApiClient, FlussApiClientCommunicationError
import pytest

from homeassistant.components.fluss import config_flow
from homeassistant.components.fluss.config_flow import (
    ApiKeyStorageHub,
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# Mock data for testing
MOCK_CONFIG = {config_flow.CONF_API_KEY: "mock_api_key"}


@pytest.fixture
async def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    return MagicMock()


async def setup_fluss_config_flow(hass: HomeAssistant, config: dict) -> dict:  # noqa: D417
    """Set up the configuration flow for Fluss.

    Args:
    - hass (HomeAssistant): The Home Assistant instance.
    - config (dict): The configuration data for setting up Fluss.

    Returns:
    - dict: Result of the configuration flow.

    """
    flow = config_flow.FlussConfigFlow()
    flow.hass = hass
    with patch.object(
        config_flow, "validate_input", return_value={"title": "Mock Title"}
    ):
        return await flow.async_step_user(config)


@pytest.mark.asyncio
async def test_apikey_storage_hub_initialization() -> None:
    """Test ApiKeyStorageHub initialization."""
    mock_api_key = "mock_api_key"
    hub = ApiKeyStorageHub(mock_api_key)
    assert hub.apikey == mock_api_key


@pytest.mark.asyncio
async def test_apikey_storage_hub_authentication() -> None:
    """Test ApiKeyStorageHub authentication."""
    mock_api_key = "mock_api_key"
    hub = ApiKeyStorageHub(mock_api_key)

    # Call the authenticate method directly to cover the line `return True`
    result = await hub.authenticate()
    assert result is True


@pytest.mark.asyncio
async def test_validate_input_success(mock_hass) -> None:
    """Test validate_input with successful authentication."""
    mock_api_key = "mock_api_key"
    data = {config_flow.CONF_API_KEY: mock_api_key}

    with (
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch.object(ApiKeyStorageHub, "authenticate", return_value=True),
    ):
        result = await validate_input(mock_hass, data)
        assert result == {"title": "Fluss+"}


@pytest.mark.asyncio
async def test_validate_input_invalid_auth(mock_hass) -> None:
    """Test validate_input with invalid authentication."""
    mock_api_key = "mock_api_key"
    data = {config_flow.CONF_API_KEY: mock_api_key}

    with (  # noqa: SIM117
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch.object(FlussApiClient, "async_validate_api_key", return_value=False),
    ):  # noqa: SIM117
        with pytest.raises(InvalidAuth):
            await validate_input(mock_hass, data)


@pytest.mark.asyncio
async def test_cannot_connect_exception(mock_hass) -> None:
    """Test handling of connection errors in validate_input."""
    mock_api_key = "mock_api_key"
    data = {config_flow.CONF_API_KEY: mock_api_key}

    # Mock async_get_clientsession to return a session and raise CannotConnect exception
    with (  # noqa: SIM117
        patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch.object(
            FlussApiClient,
            "async_validate_api_key",
            side_effect=FlussApiClientCommunicationError,
        ),
    ):
        # Ensure that CannotConnect is raised
        with pytest.raises(config_flow.CannotConnect):
            await validate_input(mock_hass, data)


@pytest.mark.asyncio
async def test_successful_initialization_and_authentication(mock_hass) -> None:
    """Test successful initialization and authentication of ApiKeyStorageHub."""
    mock_api_key = "mock_api_key"
    mock_config = {config_flow.CONF_API_KEY: mock_api_key}

    with patch.object(config_flow.ApiKeyStorageHub, "authenticate", return_value=True):
        result = await setup_fluss_config_flow(mock_hass, mock_config)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Mock Title"
        assert result["data"] == mock_config


@pytest.mark.asyncio
async def test_form_invalid_auth(mock_hass) -> None:
    """Test handling of invalid authentication."""
    with patch.object(config_flow, "validate_input", side_effect=InvalidAuth):
        flow = config_flow.FlussConfigFlow()
        flow.hass = mock_hass

        result = await flow.async_step_user(MOCK_CONFIG)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_form_cannot_connect(mock_hass) -> None:
    """Test handling of connection errors."""
    with patch.object(config_flow, "validate_input", side_effect=CannotConnect):
        flow = config_flow.FlussConfigFlow()
        flow.hass = mock_hass

        result = await flow.async_step_user(MOCK_CONFIG)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_form_unknown_error(mock_hass) -> None:
    """Test handling of unknown errors."""
    with patch.object(
        config_flow, "validate_input", side_effect=Exception("Test error")
    ):
        flow = config_flow.FlussConfigFlow()
        flow.hass = mock_hass

        result = await flow.async_step_user(MOCK_CONFIG)
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


@pytest.mark.asyncio
async def test_form_success(mock_hass) -> None:
    """Test a successful form submission."""
    result = await setup_fluss_config_flow(mock_hass, MOCK_CONFIG)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mock Title"
    assert result["data"] == MOCK_CONFIG


@pytest.mark.asyncio
async def test_show_form_on_failure(mock_hass) -> None:
    """Test that the form is re-shown with errors if an exception occurs."""
    with patch.object(
        config_flow, "validate_input", side_effect=Exception("Test error")
    ):
        flow = config_flow.FlussConfigFlow()
        flow.hass = mock_hass

        result = await flow.async_step_user(MOCK_CONFIG)
        assert result["type"] == FlowResultType.FORM
        assert "base" in result["errors"]
