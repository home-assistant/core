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
from .receiver import Receiver, async_interview
from .services import DATA_MP_ENTITIES, async_register_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class OnkyoData:
    """Config Entry data."""

    receiver: Receiver
    sources: dict[InputSource, str]
    sound_modes: dict[ListeningMode, str]


type OnkyoConfigEntry = ConfigEntry[OnkyoData]


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    """Set up Onkyo component."""
    await async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OnkyoConfigEntry) -> bool:
    """Set up the Onkyo config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))

    host = entry.data[CONF_HOST]

    info = await async_interview(host)
    if info is None:
        raise ConfigEntryNotReady(f"Unable to connect to: {host}")

    receiver = await Receiver.async_create(info)

    sources_store: dict[str, str] = entry.options[OPTION_INPUT_SOURCES]
    sources = {InputSource(k): v for k, v in sources_store.items()}

    sound_modes_store: dict[str, str] = entry.options.get(OPTION_LISTENING_MODES, {})
    sound_modes = {ListeningMode(k): v for k, v in sound_modes_store.items()}

    entry.runtime_data = OnkyoData(receiver, sources, sound_modes)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await receiver.conn.connect()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OnkyoConfigEntry) -> bool:
    """Unload Onkyo config entry."""
    del hass.data[DATA_MP_ENTITIES][entry.entry_id]

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    receiver = entry.runtime_data.receiver
    receiver.conn.close()

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: OnkyoConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
