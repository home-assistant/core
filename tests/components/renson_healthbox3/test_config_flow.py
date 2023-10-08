"""Test the Renson healthbox config flow."""
from unittest.mock import patch

from pyhealthbox3.healthbox3 import (
    Healthbox3ApiClientAuthenticationError,
    Healthbox3ApiClientCommunicationError,
    Healthbox3ApiClientError,
)

from homeassistant import config_entries
from homeassistant.components.renson_healthbox3.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "pyhealthbox3.healthbox3.Healthbox3.async_enable_advanced_api_features",
        return_value={},
    ), patch(
        "homeassistant.components.renson_healthbox3.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abc123",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Renson"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "api_key": "abc123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_without_apikey(hass: HomeAssistant) -> None:
    """Test we get the form without any api key."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.renson_healthbox3.config_flow.Healthbox3.async_validate_connectivity",
        return_value={},
    ), patch(
        "homeassistant.components.renson_healthbox3.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Renson"
    assert result2["data"] == {"host": "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_auth_error(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyhealthbox3.healthbox3.Healthbox3.async_enable_advanced_api_features",
        side_effect=Healthbox3ApiClientAuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abc123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"api_key": "auth"}


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test we handle auth error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.renson_healthbox3.config_flow.Healthbox3.async_enable_advanced_api_features",
        side_effect=Healthbox3ApiClientCommunicationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abc123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "connection"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.renson_healthbox3.config_flow.Healthbox3.async_enable_advanced_api_features",
        side_effect=Healthbox3ApiClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abc123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_unknown(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.renson_healthbox3.config_flow.Healthbox3.async_enable_advanced_api_features",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "api_key": "abc123",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
