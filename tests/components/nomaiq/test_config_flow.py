"""Test the nomaiq config flow."""

from unittest.mock import AsyncMock, patch

import ayla_iot_unofficial

from homeassistant import config_entries
from homeassistant.components.nomaiq.const import DOMAIN
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nomaiq.config_flow.ayla_iot_unofficial.AylaApi.async_sign_in"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
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
        "homeassistant.components.nomaiq.config_flow.ayla_iot_unofficial.AylaApi.async_sign_in",
        side_effect=ayla_iot_unofficial.AylaAuthError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.nomaiq.config_flow.ayla_iot_unofficial.AylaApi.async_sign_in"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
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
        "homeassistant.components.nomaiq.config_flow.ayla_iot_unofficial.AylaApi.async_sign_in",
        side_effect=ayla_iot_unofficial.AylaApiError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.nomaiq.config_flow.ayla_iot_unofficial.AylaApi.async_sign_in"
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CLIENT_ID: "test-client-id",
                CONF_CLIENT_SECRET: "test-client-secret",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_CLIENT_ID: "test-client-id",
        CONF_CLIENT_SECRET: "test-client-secret",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
