"""Test the Microsoft Speech config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.microsoft_speech.config_flow import (
    CannotConnect,
    InvalidAuth,
)
from homeassistant.components.microsoft_speech.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_NAME, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.microsoft_speech.config_flow.validate_input",
            return_value={"title": "Name of the device"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-device",
                CONF_LANGUAGE: "en-US",
                CONF_API_KEY: "test-api-key",
                CONF_REGION: "northeurope",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "test-device",
        CONF_LANGUAGE: "en-US",
        CONF_API_KEY: "test-api-key",
        CONF_REGION: "northeurope",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.microsoft_speech.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-device",
                CONF_LANGUAGE: "en-US",
                CONF_API_KEY: "test-api-key",
                CONF_REGION: "northeurope",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert len(mock_setup_entry.mock_calls) == 0

    with (
        patch(
            "homeassistant.components.microsoft_speech.config_flow.validate_input",
            return_value={"title": "Name of the device"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-device",
                CONF_LANGUAGE: "en-US",
                CONF_API_KEY: "test-api-key",
                CONF_REGION: "northeurope",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "test-device",
        CONF_LANGUAGE: "en-US",
        CONF_API_KEY: "test-api-key",
        CONF_REGION: "northeurope",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.microsoft_speech.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-device",
                CONF_LANGUAGE: "en-US",
                CONF_API_KEY: "test-api-key",
                CONF_REGION: "northeurope",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup_entry.mock_calls) == 0

    with (
        patch(
            "homeassistant.components.microsoft_speech.config_flow.validate_input",
            return_value={"title": "Name of the device"},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test-device",
                CONF_LANGUAGE: "en-US",
                CONF_API_KEY: "test-api-key",
                CONF_REGION: "northeurope",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == {
        CONF_NAME: "test-device",
        CONF_LANGUAGE: "en-US",
        CONF_API_KEY: "test-api-key",
        CONF_REGION: "northeurope",
    }
    assert len(mock_setup_entry.mock_calls) == 1
