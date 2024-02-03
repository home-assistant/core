"""Test the WireGuard config flow."""
from unittest.mock import AsyncMock, patch

import requests

from homeassistant import config_entries
from homeassistant.components.wireguard.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import mocked_requests


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch("requests.get", side_effect=mocked_requests):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "localhost"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {CONF_HOST: "localhost"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("requests.get", side_effect=requests.RequestException("error")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "localhost"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with patch("requests.get", side_effect=mocked_requests):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "localhost"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {CONF_HOST: "localhost"}
    assert len(mock_setup_entry.mock_calls) == 1
