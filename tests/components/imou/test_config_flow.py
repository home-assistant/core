"""Tests for the Imou config flow."""

from unittest.mock import AsyncMock, patch

from pyimouapi.exceptions import ImouException
import pytest

from homeassistant.components.imou.const import (
    CONF_API_URL,
    CONF_APP_ID,
    CONF_APP_SECRET,
    DOMAIN,
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
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"][CONF_APP_ID] == USER_INPUT[CONF_APP_ID]
    assert result["data"][CONF_APP_SECRET] == USER_INPUT[CONF_APP_SECRET]
    assert result["data"][CONF_API_URL] == USER_INPUT[CONF_API_URL]
    assert result["result"].unique_id == USER_INPUT[CONF_APP_ID]
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
        unique_id=USER_INPUT[CONF_APP_ID],
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


async def test_user_flow_form_initial(
    hass: HomeAssistant,
) -> None:
    """Test initial form display."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "data_schema" in result


async def test_user_flow_exception_handling(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
) -> None:
    """Test exception handling in user flow."""
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "errors" in result
    assert result["errors"]["base"] == "Connection timeout"


async def test_user_flow_different_api_urls(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test user flow with different API URL regions."""
    api_regions = ["sg", "eu", "na", "cn"]

    for idx, region in enumerate(api_regions):
        user_input = {
            CONF_APP_ID: f"{TEST_APP_ID}_{idx}",
            CONF_APP_SECRET: TEST_APP_SECRET,
            CONF_API_URL: region,
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
        assert result["data"][CONF_API_URL] == region
