"""Test initialization of ccl."""

from http import HTTPStatus
import json
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
            HTTPStatus.BAD_REQUEST,
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

    async def handler_side_effect(request, devices_dict):
        """Mock handler that validates content type and returns the expected response."""
        content_type = request.headers.get("Content-Type", "")
        if content_type and content_type != "application/json":
            return web.Response(status=HTTPStatus.BAD_REQUEST)
        return web.Response(status=HTTPStatus.OK)

    with patch(
        "homeassistant.components.ccl.CCLServer.handler",
        side_effect=handler_side_effect,
    ):
        if headers is None:
            resp = await client.post(
                urlparse(webhook_url).path,
                headers={"Content-Type": "text/plain"},
                data=json.dumps(body),
            )
        else:
            resp = await client.post(
                urlparse(webhook_url).path,
                headers=headers,
                json=body,
            )

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    assert resp.status == expected_code


async def test_webhook_registration_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ccl: MagicMock,
) -> None:
    """Test that ConfigEntryNotReady is raised when webhook registration fails."""
    hass.config.external_url = "http://example.com"
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.ccl.register_webhook",
        side_effect=ValueError("Webhook registration failed"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Config entry should not be loaded due to webhook registration failure
        assert mock_config_entry.state is not ConfigEntryState.LOADED


async def test_device_update_callback_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ccl: MagicMock,
) -> None:
    """Test that the update callback is registered with the device."""
    hass.config.external_url = "http://example.com"
    mock_config_entry.add_to_hass(hass)

    # Create a mock device with set_update_callback method
    mock_device = MagicMock()
    mock_device.device_id = "dev123"
    mock_device.name = "Test Device"
    mock_device.model = "HA100"
    mock_device.fw_ver = "1.0"
    mock_device.set_update_callback = MagicMock()

    with patch(
        "homeassistant.components.ccl.CCLDevice",
        return_value=mock_device,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify that set_update_callback was called
        assert mock_device.set_update_callback.called
