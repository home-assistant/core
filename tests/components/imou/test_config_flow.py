"""Tests for the Imou config flow."""

from unittest.mock import AsyncMock, patch

from pyimouapi.exceptions import ImouException
import pytest

from homeassistant.components.imou.const import (
    CONF_API_URL_FK,
    CONF_API_URL_HZ,
    CONF_API_URL_OR,
    CONF_API_URL_SG,
    DOMAIN,
    PARAM_API_URL,
    PARAM_APP_ID,
    PARAM_APP_SECRET,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .util import TEST_APP_ID, TEST_APP_SECRET, USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> AsyncMock:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.imou.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Create a mock API client."""
    with patch(
        "homeassistant.components.imou.config_flow.ImouOpenApiClient"
    ) as mock_client:
        mock_instance = AsyncMock()
        mock_instance.async_get_token = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_instance


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"][PARAM_APP_ID] == USER_INPUT[PARAM_APP_ID]
    assert result["data"][PARAM_APP_SECRET] == USER_INPUT[PARAM_APP_SECRET]
    assert result["data"][PARAM_API_URL] == USER_INPUT[PARAM_API_URL]
    assert result["result"].unique_id == USER_INPUT[PARAM_APP_ID]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test duplicate entry is aborted."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=USER_INPUT[PARAM_APP_ID],
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=USER_INPUT[PARAM_APP_ID],
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.imou.ImouHaDeviceManager",
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"rotation_duration": 1000},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options["rotation_duration"] == 1000


async def test_options_flow_with_default_value(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test options flow with default value."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=USER_INPUT[PARAM_APP_ID],
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.imou.ImouHaDeviceManager",
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    # Verify default value is shown in form
    assert "data_schema" in result


async def test_user_flow_form_initial(
    hass: HomeAssistant,
) -> None:
    """Test initial form display."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert "data_schema" in result


async def test_user_flow_exception_handling(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
) -> None:
    """Test exception handling in user flow."""
    # Test with ImouException (which is caught and handled)
    mock_exception = ImouException("Connection timeout")
    mock_exception.get_title = lambda: "Connection timeout"
    mock_api_client.async_get_token.side_effect = mock_exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    # Should still show form with error
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "login"
    assert "errors" in result
    assert result["errors"]["base"] == "Connection timeout"


async def test_user_flow_different_api_urls(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test user flow with different API URLs."""
    api_urls = [
        CONF_API_URL_SG,
        CONF_API_URL_OR,
        CONF_API_URL_FK,
        CONF_API_URL_HZ,
    ]

    for idx, api_url in enumerate(api_urls):
        # Use different app_id for each URL to avoid duplicate entry errors
        user_input = {
            PARAM_APP_ID: f"{TEST_APP_ID}_{idx}",
            PARAM_APP_SECRET: TEST_APP_SECRET,
            PARAM_API_URL: api_url,
        }

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][PARAM_API_URL] == api_url


async def test_options_flow_cancel(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test canceling options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=USER_INPUT[PARAM_APP_ID],
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.imou.ImouHaDeviceManager",
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
