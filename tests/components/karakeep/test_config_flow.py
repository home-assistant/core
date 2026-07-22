"""Tests for the Karakeep config flow."""

from unittest.mock import AsyncMock

from aiokarakeep import KarakeepApiError, KarakeepAuthError, KarakeepConnectionError
import pytest

from homeassistant.components.karakeep.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_TOKEN, TEST_URL

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_karakeep_client: AsyncMock) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: f"{TEST_URL}/",
            CONF_TOKEN: f" {TEST_TOKEN} ",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Karakeep"
    assert result["data"] == {
        CONF_URL: TEST_URL,
        CONF_TOKEN: TEST_TOKEN,
        CONF_VERIFY_SSL: False,
    }
    assert result["result"].unique_id is None
    mock_karakeep_client.async_get_stats.assert_awaited_once()


@pytest.mark.parametrize("invalid_url", ["karakeep.example.com", "http://["])
@pytest.mark.usefixtures("mock_setup_entry", "mock_karakeep_client")
async def test_invalid_url(hass: HomeAssistant, invalid_url: str) -> None:
    """Test invalid URL errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: invalid_url,
            CONF_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url_format"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_URL: TEST_URL,
        CONF_TOKEN: TEST_TOKEN,
        CONF_VERIFY_SSL: True,
    }


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (KarakeepAuthError("Invalid token", 401), "invalid_auth"),
        (KarakeepConnectionError("Cannot connect"), "cannot_connect"),
        (KarakeepApiError("API error", 500), "api_error"),
        (Exception("Boom"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_errors(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test config flow errors."""
    mock_karakeep_client.async_get_stats.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_karakeep_client.async_get_stats.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: TEST_URL,
            CONF_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_URL: TEST_URL,
        CONF_TOKEN: TEST_TOKEN,
        CONF_VERIFY_SSL: True,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_duplicate(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate config flow aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: f"{TEST_URL}/",
            CONF_TOKEN: TEST_TOKEN,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_karakeep_client.async_get_stats.assert_not_awaited()
