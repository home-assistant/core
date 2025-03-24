"""The denonavr component."""

import logging

from denonavr import DenonAVR
from denonavr.exceptions import AvrNetworkError, AvrTimoutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.httpx_client import get_async_client

from .const import (
    CONF_SHOW_ALL_SOURCES,
    CONF_UPDATE_AUDYSSEY,
    CONF_USE_TELNET,
    CONF_ZONE2,
    CONF_ZONE3,
    DEFAULT_SHOW_SOURCES,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_AUDYSSEY,
    DEFAULT_USE_TELNET,
    DEFAULT_ZONE2,
    DEFAULT_ZONE3,
)
from .receiver import ConnectDenonAVR

PLATFORMS = [Platform.MEDIA_PLAYER]

_LOGGER = logging.getLogger(__name__)

type DenonavrConfigEntry = ConfigEntry[DenonAVR]


async def async_setup_entry(hass: HomeAssistant, entry: DenonavrConfigEntry) -> bool:
    """Set up the denonavr components from a config entry."""
    # Connect to receiver
    connect_denonavr = ConnectDenonAVR(
        entry.data[CONF_HOST],
        DEFAULT_TIMEOUT,
        entry.options.get(CONF_SHOW_ALL_SOURCES, DEFAULT_SHOW_SOURCES),
        entry.options.get(CONF_ZONE2, DEFAULT_ZONE2),
        entry.options.get(CONF_ZONE3, DEFAULT_ZONE3),
        entry.options.get(CONF_USE_TELNET, DEFAULT_USE_TELNET),
        entry.options.get(CONF_UPDATE_AUDYSSEY, DEFAULT_UPDATE_AUDYSSEY),
        lambda: get_async_client(hass),
    )
    try:
        await connect_denonavr.async_connect_receiver()
    except (AvrNetworkError, AvrTimoutError) as ex:
        raise ConfigEntryNotReady from ex
    receiver = connect_denonavr.receiver

    entry.async_on_unload(entry.add_update_listener(update_listener))

    entry.runtime_data = receiver

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    use_telnet = entry.options.get(CONF_USE_TELNET, DEFAULT_USE_TELNET)

    async def _async_disconnect(event: Event) -> None:
        """Disconnect from Telnet."""
        if use_telnet and receiver is not None:
            await receiver.async_telnet_disconnect()

    if use_telnet:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect)
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DenonavrConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if config_entry.options.get(CONF_USE_TELNET, DEFAULT_USE_TELNET):
        receiver = config_entry.runtime_data
        await receiver.async_telnet_disconnect()

    # Remove zone2 and zone3 entities if needed
    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    unique_id = config_entry.unique_id or config_entry.entry_id
    zone2_id = f"{unique_id}-Zone2"
    zone3_id = f"{unique_id}-Zone3"
    for entry in entries:
        if entry.unique_id == zone2_id and not config_entry.options.get(CONF_ZONE2):
            entity_registry.async_remove(entry.entity_id)
            _LOGGER.debug("Removing zone2 from DenonAvr")
        if entry.unique_id == zone3_id and not config_entry.options.get(CONF_ZONE3):
            entity_registry.async_remove(entry.entity_id)
            _LOGGER.debug("Removing zone3 from DenonAvr")

    return unload_ok


async def update_listener(
    hass: HomeAssistant, config_entry: DenonavrConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
