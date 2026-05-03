"""The Open Responses integration."""

import openai

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BASE_URL, DOMAIN

PLATFORMS = (Platform.AI_TASK, Platform.CONVERSATION)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type OpenAIConfigEntry = ConfigEntry[openai.AsyncClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Open Responses."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OpenAIConfigEntry) -> bool:
    """Set up Open Responses from a config entry."""
    client = openai.AsyncOpenAI(
        api_key=entry.data[CONF_API_KEY],
        base_url=entry.data[CONF_BASE_URL],
        http_client=get_async_client(hass),
    )

    # Cache current platform data which gets added to each request (caching done by library)
    _ = await hass.async_add_executor_job(client.platform_headers)

    try:
        await client.models.list(timeout=10.0)
    except openai.AuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except openai.OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpenAIConfigEntry) -> bool:
    """Unload Open Responses."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(hass: HomeAssistant, entry: OpenAIConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
