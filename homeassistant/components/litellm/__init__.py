"""The LiteLLM integration."""

from openai import AsyncOpenAI, AuthenticationError, OpenAIError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import LOGGER

PLATFORMS = [Platform.AI_TASK, Platform.CONVERSATION]

type LiteLLMConfigEntry = ConfigEntry[AsyncOpenAI]

# LiteLLM proxies may run without authentication. The OpenAI client requires a
# non-empty API key, so we send a placeholder when the user did not provide one.
PLACEHOLDER_API_KEY = "sk-no-key-required"


async def async_setup_entry(hass: HomeAssistant, entry: LiteLLMConfigEntry) -> bool:
    """Set up LiteLLM from a config entry."""
    client = AsyncOpenAI(
        base_url=entry.data[CONF_URL],
        api_key=entry.data.get(CONF_API_KEY) or PLACEHOLDER_API_KEY,
        http_client=get_async_client(hass),
    )

    try:
        async for _ in client.with_options(timeout=10.0).models.list():
            break
    except AuthenticationError as err:
        LOGGER.error("Invalid API key: %s", err)
        raise ConfigEntryError("Invalid API key") from err
    except OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: LiteLLMConfigEntry
) -> None:
    """Handle update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LiteLLMConfigEntry) -> bool:
    """Unload LiteLLM."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
