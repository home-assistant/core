"""Test the SwitchBot via API config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.switchbot_cloud.config_flow import (
    CannotConnect,
    InvalidAuth,
)
from homeassistant.components.switchbot_cloud.const import DOMAIN, ENTRY_TITLE
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] == FlowResultType.FORM
    assert not result_init["errors"]

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        return_value=True,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                CONF_API_TOKEN: "test-token",
                CONF_API_KEY: "test-secret-key",
            },
        )
        await hass.async_block_till_done()

    assert result_configure["type"] == FlowResultType.CREATE_ENTRY
    assert result_configure["title"] == ENTRY_TITLE
    assert result_configure["data"] == {
        CONF_API_TOKEN: "test-token",
        CONF_API_KEY: "test-secret-key",
    }
    mock_setup_entry.assert_called_once()


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        side_effect=InvalidAuth,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                CONF_API_TOKEN: "test-token",
                CONF_API_KEY: "test-secret-key",
            },
        )

    assert result_configure["type"] == FlowResultType.FORM
    assert result_configure["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        side_effect=CannotConnect,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                CONF_API_TOKEN: "test-token",
                CONF_API_KEY: "test-secret-key",
            },
        )

    assert result_configure["type"] == FlowResultType.FORM
    assert result_configure["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        side_effect=Exception,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                CONF_API_TOKEN: "test-token",
                CONF_API_KEY: "test-secret-key",
            },
        )

    assert result_configure["type"] == FlowResultType.FORM
    assert result_configure["errors"] == {"base": "unknown"}
