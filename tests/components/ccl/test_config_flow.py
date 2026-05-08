"""Test the CCL Electronics config flow."""

from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from aiohttp import web

from homeassistant import config_entries
from homeassistant.components.ccl.const import DOMAIN
from homeassistant.components.webhook import async_generate_url
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import WEBHOOK_ID

from tests.typing import ClientSessionGenerator


async def test_create_entry(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_ccl: MagicMock,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test we can create a config entry."""
    hass.config.external_url = "http://example.com"
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "webhook", {})

    with patch(
        "homeassistant.components.webhook.async_generate_id", return_value=WEBHOOK_ID
    ):
        # Initial step should return SHOW_PROGRESS while waiting for device update
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "user"

        # Simulate successful webhook request
        client = await hass_client_no_auth()
        webhook_url = async_generate_url(hass, WEBHOOK_ID)
        body = {"hello": "world"}

        def handler_side_effect(request, devices_dict):
            # Simulate the handler setting last_update_time
            device = devices_dict[WEBHOOK_ID]
            device.last_update_time = 123
            return web.Response(status=200)

        with patch(
            "homeassistant.components.ccl.CCLServer.handler",
            side_effect=handler_side_effect,
        ):
            resp = await client.post(urlparse(webhook_url).path, json=body)

        assert resp.status == 200

        # Wait for the background task to complete after webhook is posted
        await hass.async_block_till_done()

        # After device updates, configure to complete the flow
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_WEBHOOK_ID] == WEBHOOK_ID
        assert len(mock_setup_entry.mock_calls) == 1
