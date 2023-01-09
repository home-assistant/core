"""Support for Google Assistant SDK."""
from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .helpers import async_send_text_commands

SERVICE_SEND_TEXT_COMMAND = "send_text_command"
SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND = "command"
SERVICE_SEND_TEXT_COMMAND_SCHEMA = vol.All(
    {
        vol.Required(SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND): vol.All(
            str, vol.Length(min=1)
        ),
    },
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Assistant SDK component."""
    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.NOTIFY, DOMAIN, {CONF_NAME: DOMAIN}, config
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Assistant SDK from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = session

    await async_setup_service(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state == ConfigEntryState.LOADED
    ]
    if len(loaded_entries) == 1:
        for service_name in hass.services.async_services()[DOMAIN]:
            hass.services.async_remove(DOMAIN, service_name)

    return True


async def async_setup_service(hass: HomeAssistant) -> None:
    """Add the services for Google Assistant SDK."""

    async def send_text_command(call: ServiceCall) -> None:
        """Send a text command to Google Assistant SDK."""
        command: str = call.data[SERVICE_SEND_TEXT_COMMAND_FIELD_COMMAND]
        await async_send_text_commands([command], hass)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_TEXT_COMMAND,
        send_text_command,
        schema=SERVICE_SEND_TEXT_COMMAND_SCHEMA,
    )
