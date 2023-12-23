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


async def _fill_out_form_and_assert_entry_created(
    hass: HomeAssistant, flow_id: str, mock_setup_entry: AsyncMock
) -> None:
    """Util function to fill out a form and assert that a config entry is created."""
    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        return_value=[],
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            flow_id,
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


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result_init["type"] == FlowResultType.FORM
    assert not result_init["errors"]

    await _fill_out_form_and_assert_entry_created(
        hass, result_init["flow_id"], mock_setup_entry
    )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (InvalidAuth, "invalid_auth"),
        (CannotConnect, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_fails(
    hass: HomeAssistant, error: Exception, message: str, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle error cases."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.switchbot_cloud.config_flow.SwitchBotAPI.list_devices",
        side_effect=error,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                CONF_API_TOKEN: "test-token",
                CONF_API_KEY: "test-secret-key",
            },
        )

        assert result_configure["type"] == FlowResultType.FORM
        assert result_configure["errors"] == {"base": message}
        await hass.async_block_till_done()

    await _fill_out_form_and_assert_entry_created(
        hass, result_init["flow_id"], mock_setup_entry
    )
