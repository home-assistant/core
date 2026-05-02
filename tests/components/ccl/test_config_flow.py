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

    with patch("secrets.token_hex", return_value=WEBHOOK_ID):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
        assert result["step_id"] == "finish"

        # Simulate successful webhook request
        client = await hass_client_no_auth()
        webhook_url = async_generate_url(hass, WEBHOOK_ID)
        body = {"hello": "world"}

        def handler_side_effect(request, devices_dict):
            # Simulate the handler setting last_update_time
            device = devices_dict[WEBHOOK_ID]
            device.last_update_time = 12345
            return web.Response(status=200)

        with patch("aioccl.CCLServer.handler", side_effect=handler_side_effect):
            resp = await client.post(urlparse(webhook_url).path, json=body)

        assert resp.status == 200

        # Wait for the task to complete
        await hass.async_block_till_done()

        # Configure again to complete the flow
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(result["data"][CONF_WEBHOOK_ID]) == 8
    assert len(mock_setup_entry.mock_calls) == 1
