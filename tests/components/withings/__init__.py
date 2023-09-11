"""Tests for the withings component."""
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from homeassistant.components.webhook import async_generate_url
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@dataclass
class WebhookResponse:
    """Response data from a webhook."""

    message: str
    message_code: int


async def call_webhook(
    hass: HomeAssistant, webhook_id: str, data: dict[str, Any], client
) -> WebhookResponse:
    """Call the webhook."""
    webhook_url = async_generate_url(hass, webhook_id)

    resp = await client.post(
        urlparse(webhook_url).path,
        data=data,
    )

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    data: dict[str, Any] = await resp.json()
    resp.close()

    return WebhookResponse(message=data["message"], message_code=data["code"])


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
