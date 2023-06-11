"""Test the OVOS config flow."""
from unittest.mock import patch

import aiohttp

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.ovos.const import DOMAIN
from homeassistant.const import CONF_PORT, CONF_URL
from homeassistant.core import HomeAssistant

FIXTURE_USER_INPUT = {CONF_URL: "http://localhost", CONF_PORT: 8181}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ovos.config_flow.OvosNotificationService.authenticate",
        side_effect=aiohttp.ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_full_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ovos.config_flow.OvosNotificationService.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.ovos.config_flow.OvosNotificationService.username",
        "some_name",
    ), patch(
        "homeassistant.components.ovos.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    assert result2["data"][CONF_PORT] == FIXTURE_USER_INPUT[CONF_PORT]
