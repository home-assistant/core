"""The xbox integration."""

from __future__ import annotations

import logging

from xbox.webapi.api.client import XboxLiveClient
from xbox.webapi.api.provider.smartglass.models import SmartglassConsoleList
from xbox.webapi.common.signed_session import SignedSession

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api
from .const import DOMAIN
from .coordinator import XboxConfigEntry, XboxUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    """Set up xbox from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    signed_session = await hass.async_add_executor_job(SignedSession)
    auth = api.AsyncConfigEntryAuth(signed_session, session)

    client = XboxLiveClient(auth)
    consoles: SmartglassConsoleList = await client.smartglass.get_console_list()
    _LOGGER.debug(
        "Found %d consoles: %s",
        len(consoles.result),
        consoles.model_dump(),
    )

    coordinator = XboxUpdateCoordinator(hass, entry, client, consoles)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: XboxConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
