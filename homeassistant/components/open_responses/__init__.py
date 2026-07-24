"""The Open Responses integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .client import AsyncOpenResponsesClient
from .const import CONF_BASE_URL, DOMAIN
from .helpers import client_base_url

PLATFORMS = (Platform.CONVERSATION,)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type OpenResponsesConfigEntry = ConfigEntry[AsyncOpenResponsesClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Open Responses."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenResponsesConfigEntry
) -> bool:
    """Set up Open Responses from a config entry."""
    client = AsyncOpenResponsesClient(
        api_key=entry.data[CONF_API_KEY],
        base_url=client_base_url(entry.data[CONF_BASE_URL]),
        http_client=get_async_client(hass),
    )

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenResponsesConfigEntry
) -> bool:
    """Unload Open Responses."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_options(
    hass: HomeAssistant, entry: OpenResponsesConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)
