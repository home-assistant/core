"""The Open Responses integration."""

from contextlib import suppress

from openresponses_client import (
    AuthenticationError,
    BadRequestError,
    OpenResponsesClient,
    OpenResponsesError,
    PermissionDeniedError,
    UnprocessableEntityError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS = (Platform.CONVERSATION,)

type OpenResponsesConfigEntry = ConfigEntry[OpenResponsesClient]


async def async_check_connection(client: OpenResponsesClient) -> None:
    """Check that the server is reachable and accepts the credentials."""
    # Servers reject an empty request only after authenticating it
    with suppress(BadRequestError, UnprocessableEntityError):
        await client.create(timeout=10)


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenResponsesConfigEntry
) -> bool:
    """Set up Open Responses from a config entry."""
    client = OpenResponsesClient(
        entry.data[CONF_URL],
        api_key=entry.data.get(CONF_API_KEY),
        session=async_get_clientsession(hass),
    )
    try:
        await async_check_connection(client)
    except (AuthenticationError, PermissionDeniedError) as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except OpenResponsesError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err

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
    """Reload the entry when its subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)
