"""Test the Sunsynk Inverter Web config flow."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant import config_entries
from homeassistant.components.sunsynkweb.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    basicdata,
    sessiongetter,
    basic_flow,
):
    """Validate the one form in the config flow."""
    sessiongetter.json.side_effect = basicdata
    result = await hass.config_entries.flow.async_configure(
        basic_flow["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sunsynk web data"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    basicdata,
    sessiongetter,
    basic_flow,
) -> None:
    """Test we handle invalid auth."""

    sessiongetter.json.side_effect = [{"msg": "failed", "data": {"blah": "failed"}}]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"username": "invalid", "password": "invalid"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    sessiongetter.json.side_effect = basicdata
    result = await hass.config_entries.flow.async_configure(
        basic_flow["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sunsynk web data"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    basicdata,
    sessiongetter,
    basic_flow,
) -> None:
    """Test we handle cannot connect error."""

    sessiongetter.json.side_effect = aiohttp.ClientConnectionError
    result = await hass.config_entries.flow.async_configure(
        basic_flow["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    sessiongetter.json.side_effect = basicdata
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sunsynk web data"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_unepxected(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    basicdata,
    basic_flow,
    sessiongetter,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    sessiongetter.json.side_effect = Exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
