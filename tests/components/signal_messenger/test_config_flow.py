"""Test the signal_messenger config flow."""

from unittest.mock import patch

import requests
from requests_mock import Mocker

from homeassistant import config_entries
from homeassistant.components.signal_messenger.const import (
    CONF_RECP_NR,
    CONF_SENDER_NR,
    CONF_SIGNAL_CLI_REST_API,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_user_success(hass: HomeAssistant) -> None:
    """Test we get the user form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "requests.get",
        ) as mock_request_get,
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = "{}"
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "My Signal",
                CONF_SIGNAL_CLI_REST_API: "http://127.0.0.1:8123/",
                CONF_SENDER_NR: "+1234567890",
                CONF_RECP_NR: "+0987654321 +1122334455",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Signal My Signal"
    assert result2["data"] == {
        CONF_NAME: "My Signal",
        CONF_SIGNAL_CLI_REST_API: "http://127.0.0.1:8123/",
        CONF_SENDER_NR: "+1234567890",
        CONF_RECP_NR: ["+0987654321", "+1122334455"],
    }
    assert len(hass.services.async_services()) == 1
    assert hass.services.has_service("notify", "signal_my_signal")


async def test_form_user_can_not_connect(
    hass: HomeAssistant,
    requests_mock: Mocker,
) -> None:
    """Test we get the user form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    requests_mock.get("http://127.0.0.1:8123/v1/about", exc=requests.ConnectionError)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "My Signal",
            CONF_SIGNAL_CLI_REST_API: "http://127.0.0.1:8123",
            CONF_SENDER_NR: "+1234567890",
            CONF_RECP_NR: "+0987654321 +1122334455",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("step_id") == "user"
    assert result2.get("errors") == {"base": "cannot_connect"}
