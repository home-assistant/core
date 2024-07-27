"""The bluesound component."""

from dataclasses import dataclass
from typing import NamedTuple

import aiohttp
from pyblu import Player, SyncStatus
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
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

PLATFORMS = [Platform.MEDIA_PLAYER]

BS_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

BS_JOIN_SCHEMA = BS_SCHEMA.extend({vol.Required(ATTR_MASTER): cv.entity_id})

class ServiceMethodDetails(NamedTuple):
    """Details for SERVICE_TO_METHOD mapping."""

    method: str
    schema: vol.Schema

SERVICE_TO_METHOD = {
    SERVICE_JOIN: ServiceMethodDetails(method="async_join", schema=BS_JOIN_SCHEMA),
    SERVICE_UNJOIN: ServiceMethodDetails(method="async_unjoin", schema=BS_SCHEMA),
    SERVICE_SET_TIMER: ServiceMethodDetails(
        method="async_increase_timer", schema=BS_SCHEMA
    ),
    SERVICE_CLEAR_TIMER: ServiceMethodDetails(
        method="async_clear_timer", schema=BS_SCHEMA
    ),
}

@dataclass
class BluesoundData:
    """Bluesound data class."""

    player: Player
    sync_status: SyncStatus


type BluesoundConfigEntry = ConfigEntry[BluesoundData]

def setup_services(hass: HomeAssistant) -> None:
    """Set up services for Bluesound component."""

    async def async_service_handler(service: ServiceCall) -> None:
        """Map services to method of Bluesound devices."""
        if not (method := SERVICE_TO_METHOD.get(service.service)):
            return

        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            target_players = [
                player
                for player in hass.data[DOMAIN]
                if player.entity_id in entity_ids
            ]
        else:
            target_players = hass.data[DOMAIN]

        for player in target_players:
            await getattr(player, method.method)(**params)

    for service, method in SERVICE_TO_METHOD.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=method.schema
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Bluesound."""
    await setup_services(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: BluesoundConfigEntry
) -> bool:
    """Set up the Bluesound entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    session = async_get_clientsession(hass)
    async with Player(host, port, session=session, default_timeout=10) as player:
        try:
            sync_status = await player.sync_status(timeout=1)
        except TimeoutError as ex:
            raise ConfigEntryNotReady(f"Timeout while connecting to {host}:{port}") from ex
        except aiohttp.ClientConnectorError as ex:
            raise ConfigEntryNotReady(f"Error connecting to {host}:{port}") from ex

    config_entry.runtime_data = BluesoundData(player, sync_status)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    player = None
    for player in hass.data[DOMAIN]:
        if player.unique_id == config_entry.unique_id:
            break

    if player is None:
        return False

    player.stop_polling()
    hass.data[DOMAIN].remove(player)

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
