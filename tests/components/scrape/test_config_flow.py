"""Test the Scrape config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.scrape import DOMAIN
from homeassistant.components.scrape.const import CONF_INDEX, CONF_SELECT
from homeassistant.const import (
    CONF_METHOD,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from . import MockRestData


async def test_form(hass: HomeAssistant, get_data: MockRestData) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    with patch(
        "homeassistant.components.rest.RestData",
        return_value=get_data,
    ) as mock_data, patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )
        await hass.async_block_till_done()
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["version"] == 1
    assert result3["options"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        "sensors": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            }
        ],
    }

    assert len(mock_data.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_fails(hass: HomeAssistant, get_data: MockRestData) -> None:
    """Test config flow error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.rest.RestData",
        side_effect=HomeAssistantError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )

    assert result2["errors"] == {"base": "resource_error"}

    with patch("homeassistant.components.rest.RestData", return_value=get_data,), patch(
        "homeassistant.components.scrape.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_RESOURCE: "https://www.home-assistant.io",
                CONF_METHOD: "GET",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 10.0,
            },
        )
        await hass.async_block_till_done()
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "https://www.home-assistant.io"
    assert result4["options"] == {
        CONF_RESOURCE: "https://www.home-assistant.io",
        CONF_METHOD: "GET",
        CONF_VERIFY_SSL: True,
        CONF_TIMEOUT: 10.0,
        "sensors": [
            {
                CONF_NAME: "Current version",
                CONF_SELECT: ".current-version h1",
                CONF_INDEX: 0.0,
            }
        ],
    }
