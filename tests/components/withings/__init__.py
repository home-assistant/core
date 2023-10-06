"""Tests for the withings component."""
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.webhook import async_generate_url
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


@dataclass
class WebhookResponse:
    """Response data from a webhook."""

    message: str
    message_code: int


async def call_webhook(
    hass: HomeAssistant, webhook_id: str, data: dict[str, Any], client: TestClient
) -> WebhookResponse:
    """Call the webhook."""
    webhook_url = async_generate_url(hass, webhook_id)

    resp = await client.post(
        urlparse(webhook_url).path,
        data=data,
    )

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()

    data = await resp.json()
    resp.close()

    return WebhookResponse(message=data["message"], message_code=data["code"])


async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, enable_webhooks: bool = True
) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    if enable_webhooks:
        await async_process_ha_core_config(
            hass,
            {"external_url": "https://example.local:8123"},
        )

    await hass.config_entries.async_setup(config_entry.entry_id)


async def prepare_webhook_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Prepare webhooks are registered by waiting a second."""
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
