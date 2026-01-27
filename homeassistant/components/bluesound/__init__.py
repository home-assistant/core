"""The bluesound component."""

from pyblu import Player
from pyblu.errors import PlayerUnreachableError
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_MASTER,
    DOMAIN,
    SERVICE_CLEAR_TIMER,
    SERVICE_JOIN,
    SERVICE_SET_TIMER,
    SERVICE_UNJOIN,
)
from .coordinator import (
    BluesoundConfigEntry,
    BluesoundCoordinator,
    BluesoundRuntimeData,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bluesound."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_increase_timer",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_TIMER,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_clear_timer",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_JOIN,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={vol.Required(ATTR_MASTER): cv.entity_id},
        func="async_bluesound_join",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_UNJOIN,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="async_bluesound_unjoin",
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: BluesoundConfigEntry
) -> bool:
    """Set up the Bluesound entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    session = async_get_clientsession(hass)
    player = Player(host, port, session=session, default_timeout=10)
    try:
        sync_status = await player.sync_status(timeout=1)
    except PlayerUnreachableError as ex:
        raise ConfigEntryNotReady(f"Error connecting to {host}:{port}") from ex

    coordinator = BluesoundCoordinator(hass, config_entry, player, sync_status)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = BluesoundRuntimeData(player, sync_status, coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
