"""The onkyo component."""

import asyncio
from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    OPTION_INPUT_SOURCES,
    OPTION_LISTENING_MODES,
    InputSource,
    ListeningMode,
)
from .receiver import ReceiverManager, async_interview
from .services import DATA_MP_ENTITIES, async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class OnkyoData:
    """Config Entry data."""

    manager: ReceiverManager
    sources: dict[InputSource, str]
    sound_modes: dict[ListeningMode, str]


type OnkyoConfigEntry = ConfigEntry[OnkyoData]


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up Onkyo component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OnkyoConfigEntry) -> bool:
    """Set up the Onkyo config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))

    host = entry.data[CONF_HOST]

    try:
        info = await async_interview(host)
    except OSError as exc:
        raise ConfigEntryNotReady(f"Unable to connect to: {host}") from exc
    if info is None:
        raise ConfigEntryNotReady(f"Unable to connect to: {host}")

    manager = ReceiverManager(hass, entry, info)

    sources_store: dict[str, str] = entry.options[OPTION_INPUT_SOURCES]
    sources = {InputSource(k): v for k, v in sources_store.items()}

    sound_modes_store: dict[str, str] = entry.options.get(OPTION_LISTENING_MODES, {})
    sound_modes = {ListeningMode(k): v for k, v in sound_modes_store.items()}

    entry.runtime_data = OnkyoData(manager, sources, sound_modes)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    manager_task = entry.async_create_background_task(
        hass, manager.run(), "run_connection"
    )
    wait_for_started_task = asyncio.create_task(manager.started.wait())
    done, _ = await asyncio.wait(
        (manager_task, wait_for_started_task), return_when=asyncio.FIRST_COMPLETED
    )
    if manager_task in done:
        # Something went wrong, so let's error out here by awaiting the task
        try:
            await manager_task
        except OSError as exc:
            raise ConfigEntryNotReady(f"Unable to connect to: {host}") from exc

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OnkyoConfigEntry) -> bool:
    """Unload Onkyo config entry."""
    del hass.data[DATA_MP_ENTITIES][entry.entry_id]
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # the connection will be automatically closed when the background task is cancelled


async def update_listener(hass: HomeAssistant, entry: OnkyoConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
