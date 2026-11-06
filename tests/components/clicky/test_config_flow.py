"""Test the Clicky Web Analytics config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError
from pyclicky import (
    AuthenticationError,
    ClickyAPIError,
    ConnectionError,
    InvalidEndpoint,
    ServiceUnavailable,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.clicky.const import CONF_SITE_ID, CONF_SITEKEY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_SITE_ID, TEST_SITEKEY


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test that we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_ID
    assert result["data"] == {
        CONF_SITE_ID: TEST_SITE_ID,
        CONF_SITEKEY: TEST_SITEKEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error", "expected_placeholders"),
    [
        (AuthenticationError(), "invalid_auth", {}),
        (ConnectionError(), "cannot_connect", {}),
        (InvalidEndpoint(), "cannot_connect", {}),
        (ServiceUnavailable(), "cannot_connect", {}),
        (ClientError(), "cannot_connect", {}),
        (TimeoutError(), "cannot_connect", {}),
        (ClickyAPIError("Some API error"), "api_error", {"error": "Some API error"}),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
    expected_placeholders: dict[str, str],
) -> None:
    """Test that errors are shown and the flow can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ) as mock_lib:
        client = mock_lib.return_value
        client.visitors_online.side_effect = side_effect

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert result["description_placeholders"] == expected_placeholders
    assert len(mock_setup_entry.mock_calls) == 0

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SITE_ID
    assert result["data"] == {
        CONF_SITE_ID: TEST_SITE_ID,
        CONF_SITEKEY: TEST_SITEKEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate_site_id(hass: HomeAssistant) -> None:
    """Test that duplicate site IDs abort the config flow."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: TEST_SITE_ID,
            CONF_SITEKEY: "different_sitekey",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    with patch(
        "homeassistant.components.clicky.config_flow.ClickyClient", autospec=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SITE_ID: TEST_SITE_ID,
                CONF_SITEKEY: TEST_SITEKEY,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
