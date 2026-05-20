"""The OVHcloud AI Endpoints integration."""

from openai import AsyncOpenAI, OpenAIError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client

from .const import BASE_URL

PLATFORMS = [Platform.CONVERSATION]

type OVHcloudAIEndpointsConfigEntry = ConfigEntry[AsyncOpenAI]


def _create_client(hass: HomeAssistant, api_key: str) -> AsyncOpenAI:
    """Create the AsyncOpenAI client used by this integration."""
    return AsyncOpenAI(
        base_url=BASE_URL,
        api_key=api_key,
        http_client=get_async_client(hass),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: OVHcloudAIEndpointsConfigEntry
) -> bool:
    """Set up OVHcloud AI Endpoints from a config entry."""
    client = _create_client(hass, entry.data[CONF_API_KEY])

    try:
        # Unfortunately I couldn't find an endpoint that would authenticate the key
        # without calling an LLM. This always succeeds regardless of auth.
        async for _ in client.with_options(timeout=10.0).models.list():
            break
    except OpenAIError as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_entry(
    hass: HomeAssistant, entry: OVHcloudAIEndpointsConfigEntry
) -> None:
    """Reload the entry when its data or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: OVHcloudAIEndpointsConfigEntry
) -> bool:
    """Unload OVHcloud AI Endpoints."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
