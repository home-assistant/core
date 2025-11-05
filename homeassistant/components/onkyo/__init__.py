"""The onkyo component."""

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

    host = entry.data[CONF_HOST]

    try:
        info = await async_interview(host)
    except TimeoutError as exc:
        raise ConfigEntryNotReady(f"Timed out interviewing: {host}") from exc
    except OSError as exc:
        raise ConfigEntryNotReady(f"Unexpected exception interviewing: {host}") from exc

    manager = ReceiverManager(hass, entry, info)

    sources_store: dict[str, str] = entry.options[OPTION_INPUT_SOURCES]
    sources = {InputSource(k): v for k, v in sources_store.items()}

    sound_modes_store: dict[str, str] = entry.options.get(OPTION_LISTENING_MODES, {})
    sound_modes = {ListeningMode(k): v for k, v in sound_modes_store.items()}

    entry.runtime_data = OnkyoData(manager, sources, sound_modes)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if error := await manager.start():
        try:
            await error
        except OSError as exc:
            raise ConfigEntryNotReady(f"Unable to connect to: {host}") from exc

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OnkyoConfigEntry) -> bool:
    """Unload Onkyo config entry."""
    del hass.data[DATA_MP_ENTITIES][entry.entry_id]

    entry.runtime_data.manager.start_unloading()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
