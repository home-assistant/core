"""Test the Axion DMX config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.axion_dmx.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.axion_dmx.const import (
    CONF_CHANNEL,
    CONF_LIGHT_TYPE,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.axion_dmx.config_flow.AxionDmxApi.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "RGB",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Axion DMX Light - Channel 1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_CHANNEL: 1,
        CONF_LIGHT_TYPE: "RGB",
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
        "homeassistant.components.axion_dmx.config_flow.AxionDmxApi.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "RGB",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.axion_dmx.config_flow.AxionDmxApi.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "RGB",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Axion DMX Light - Channel 1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_CHANNEL: 1,
        CONF_LIGHT_TYPE: "RGB",
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
        "homeassistant.components.axion_dmx.config_flow.AxionDmxApi.authenticate",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "RGB",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.axion_dmx.config_flow.AxionDmxApi.authenticate",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PASSWORD: "test-password",
                CONF_CHANNEL: 1,
                CONF_LIGHT_TYPE: "RGB",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Axion DMX Light - Channel 1"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test-password",
        CONF_CHANNEL: 1,
        CONF_LIGHT_TYPE: "RGB",
    }
    assert len(mock_setup_entry.mock_calls) == 1
