"""Test the WebDAV config flow."""

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.webdav.const import CONF_BACKUP_PATH, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(hass: HomeAssistant, webdav_client: AsyncMock) -> None:
    """Test we get the form and create a entry on success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
            CONF_BACKUP_PATH: "/backups",
            CONF_VERIFY_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@webdav.demo"
    assert result["data"] == {
        CONF_URL: "https://webdav.demo",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "supersecretpassword",
        CONF_BACKUP_PATH: "/backups",
        CONF_VERIFY_SSL: False,
    }
    assert len(webdav_client.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_fail(hass: HomeAssistant, webdav_client: AsyncMock) -> None:
    """Test to handle exceptions."""
    webdav_client.check.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # reset and test for success
    webdav_client.check.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@webdav.demo"
    assert "errors" not in result
