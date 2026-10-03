"""The Mistral AI integration."""

from httpx import HTTPError
from mistralai.client import Mistral, errors

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import async_create_client
from .const import DOMAIN

__all__ = ["DOMAIN", "MistralAIConfigEntry"]

PLATFORMS = (Platform.CONVERSATION,)

type MistralAIConfigEntry = ConfigEntry[Mistral]


async def async_setup_entry(hass: HomeAssistant, entry: MistralAIConfigEntry) -> bool:
    """Set up Mistral AI from a config entry."""
    try:
        client = await async_create_client(hass, entry.data[CONF_API_KEY])
        await client.models.list_async(timeout_ms=10_000)
    except errors.MistralError as err:
        if err.status_code in (401, 403):
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err
    except (errors.NoResponseError, HTTPError) as err:
        raise ConfigEntryNotReady(err) from err

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: MistralAIConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
