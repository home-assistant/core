"""The Cloudflare Workers AI integration."""

from __future__ import annotations

import logging

from cloudflare import AsyncCloudflare

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client

from .client import (
    CloudflareAIAuthError,
    CloudflareAIClient,
    CloudflareAIConnectionError,
)
from .const import (
    CONF_ACCOUNT_ID,
    CONF_API_TOKEN,
    CONF_GATEWAY_API_TOKEN,
    CONF_GATEWAY_ID,
    CONF_USE_AI_GATEWAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (Platform.CONVERSATION,)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type CloudflareAIConfigEntry = ConfigEntry[CloudflareAIClient]


async def async_setup_entry(
    hass: HomeAssistant, entry: CloudflareAIConfigEntry
) -> bool:
    """Set up Cloudflare Workers AI from a config entry."""
    api_token = entry.data[CONF_API_TOKEN]

    httpx_client = get_async_client(hass)

    # Create the official Cloudflare SDK client
    cf = AsyncCloudflare(
        api_token=api_token,
        http_client=httpx_client,
    )

    gateway_id = None
    gateway_api_token = None
    if entry.data.get(CONF_USE_AI_GATEWAY):
        gateway_id = entry.data.get(CONF_GATEWAY_ID)
        gateway_api_token = entry.data.get(CONF_GATEWAY_API_TOKEN)

    client = CloudflareAIClient(
        cf=cf,
        httpx_client=httpx_client,
        account_id=entry.data[CONF_ACCOUNT_ID],
        api_token=api_token,
        gateway_id=gateway_id,
        gateway_api_token=gateway_api_token,
    )

    # Validate credentials before proceeding (test-before-setup)
    try:
        await client.validate_credentials()
    except CloudflareAIAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except CloudflareAIConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload entry when options are changed
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: CloudflareAIConfigEntry
) -> None:
    """Handle config entry updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: CloudflareAIConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
