"""Test initialization of ccl."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from aiohttp import web
import pytest

from homeassistant.components.webhook import async_generate_url
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import WEBHOOK_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    (
        "headers",
        "expected_code",
    ),
    [
        (
            {"Content-Type": "application/json"},
            HTTPStatus.OK,
        ),
        (
            None,
            HTTPStatus.OK,
        ),
        (
            {"Content-Type": "text/html"},
            HTTPStatus.BAD_REQUEST,
        ),
    ],
)
async def test_webhook_post(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ccl: MagicMock,
    hass_client_no_auth: ClientSessionGenerator,
    headers: dict[str, str] | None,
    expected_code: HTTPStatus,
) -> None:
    """Test webhook callback."""
    hass.config.external_url = "http://example.com"
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client_no_auth()
    webhook_url = async_generate_url(hass, WEBHOOK_ID)
    body = {"Hello": "World"}

    def handler_side_effect(request, devices_dict):
        """Mock handler that validates content type and returns the expected response."""
        if request.content_type != "application/json":
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        return web.Response(status=HTTPStatus.OK)

    with patch(
        "homeassistant.components.ccl.CCLServer.handler",
        side_effect=handler_side_effect,
    ):
        resp = await client.post(urlparse(webhook_url).path, headers=headers, json=body)

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    assert resp.status == expected_code
