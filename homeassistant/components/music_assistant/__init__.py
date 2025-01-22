"""Music Assistant (music-assistant.io) integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from music_assistant_client import MusicAssistantClient
from music_assistant_client.exceptions import CannotConnect, InvalidServerVersion
from music_assistant_models.enums import EventType
from music_assistant_models.errors import MusicAssistantError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .actions import register_actions
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from music_assistant_models.event import MassEvent

    from homeassistant.helpers.typing import ConfigType

PLATFORMS = [Platform.MEDIA_PLAYER]

CONNECT_TIMEOUT = 10
LISTEN_READY_TIMEOUT = 30

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MusicAssistantConfigEntry = ConfigEntry[MusicAssistantEntryData]


@dataclass
class MusicAssistantEntryData:
    """Hold Mass data for the config entry."""

    mass: MusicAssistantClient
    listen_task: asyncio.Task


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Music Assistant component."""
    register_actions(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MusicAssistantConfigEntry
) -> bool:
    """Set up Music Assistant from a config entry."""
    http_session = async_get_clientsession(hass, verify_ssl=False)
    mass_url = entry.data[CONF_URL]
    mass = MusicAssistantClient(mass_url, http_session)

    try:
        async with asyncio.timeout(CONNECT_TIMEOUT):
            await mass.connect()
    except (TimeoutError, CannotConnect) as err:
        raise ConfigEntryNotReady(
            f"Failed to connect to music assistant server {mass_url}"
        ) from err
    except InvalidServerVersion as err:
        async_create_issue(
            hass,
            DOMAIN,
            "invalid_server_version",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key="invalid_server_version",
        )
        raise ConfigEntryNotReady(f"Invalid server version: {err}") from err
    except MusicAssistantError as err:
        LOGGER.exception("Failed to connect to music assistant server", exc_info=err)
        raise ConfigEntryNotReady(
            f"Unknown error connecting to the Music Assistant server {mass_url}"
        ) from err

    async_delete_issue(hass, DOMAIN, "invalid_server_version")

    async def on_hass_stop(event: Event) -> None:
        """Handle incoming stop event from Home Assistant."""
        await mass.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, on_hass_stop)
    )

    # launch the music assistant client listen task in the background
    # use the init_ready event to wait until initialization is done
    init_ready = asyncio.Event()
    listen_task = asyncio.create_task(_client_listen(hass, entry, mass, init_ready))

    try:
        async with asyncio.timeout(LISTEN_READY_TIMEOUT):
            await init_ready.wait()
    except TimeoutError as err:
        listen_task.cancel()
        raise ConfigEntryNotReady("Music Assistant client not ready") from err

    # store the listen task and mass client in the entry data
    entry.runtime_data = MusicAssistantEntryData(mass, listen_task)

    # If the listen task is already failed, we need to raise ConfigEntryNotReady
    if listen_task.done() and (listen_error := listen_task.exception()) is not None:
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        try:
            await mass.disconnect()
        finally:
            raise ConfigEntryNotReady(listen_error) from listen_error

    # initialize platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # register listener for removed players
    async def handle_player_removed(event: MassEvent) -> None:
        """Handle Mass Player Removed event."""
        if event.object_id is None:
            return
        dev_reg = dr.async_get(hass)
        if hass_device := dev_reg.async_get_device({(DOMAIN, event.object_id)}):
            dev_reg.async_update_device(
                hass_device.id, remove_config_entry_id=entry.entry_id
            )

    entry.async_on_unload(
        mass.subscribe(handle_player_removed, EventType.PLAYER_REMOVED)
    )

    return True


async def _client_listen(
    hass: HomeAssistant,
    entry: ConfigEntry,
    mass: MusicAssistantClient,
    init_ready: asyncio.Event,
) -> None:
    """Listen with the client."""
    try:
        await mass.start_listening(init_ready)
    except MusicAssistantError as err:
        if entry.state != ConfigEntryState.LOADED:
            raise
        LOGGER.error("Failed to listen: %s", err)
    except Exception as err:  # pylint: disable=broad-except
        # We need to guard against unknown exceptions to not crash this task.
        if entry.state != ConfigEntryState.LOADED:
            raise
        LOGGER.exception("Unexpected exception: %s", err)

    if not hass.is_stopping:
        LOGGER.debug("Disconnected from server. Reloading integration")
        hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        mass_entry_data: MusicAssistantEntryData = entry.runtime_data
        mass_entry_data.listen_task.cancel()
        await mass_entry_data.mass.disconnect()

    return unload_ok
