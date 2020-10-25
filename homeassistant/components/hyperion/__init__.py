"""The Hyperion component."""

import asyncio
import logging
from typing import Any, Dict, Tuple

from hyperion import client, const as hyperion_const

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_ROOT_CLIENT, DOMAIN, SIGNAL_INSTANCES_UPDATED

PLATFORMS = [LIGHT_DOMAIN]

_LOGGER = logging.getLogger(__name__)

# Unique ID
# =========
# A config entry represents a connection to a single Hyperion server. The config
# entry_id is the server id returned from the Hyperion instance (a unique ID per
# server).
#
# Each server connection may create multiple entities, 1 per "instance" on the Hyperion
# server. The unique_id for each entity is <server id>_<instance #>, where <server_id>
# will be the unique_id on the relevant config entry (as above).
#
# The get_hyperion_unique_id method will create a per-entity unique id when given the
# server id and the instance number. The split_hyperion_unique_id will reverse the
# operation.

# hass.data format
# ================
#
# hass.data[DOMAIN] = {
#     <config_entry.entry_id>: {
#         "ROOT_CLIENT": <Hyperion Client>
#         "LIGHT": {
#             "ENTITIES": {<unique_id>: <entity>}
#             "DISPATCHER_UNSUB": <dispatcher unsubscribe callable>
#         }
#     }
# }


def get_hyperion_unique_id(server_id: str, instance: int) -> str:
    """Get a unique_id for a Hyperion instance."""
    return f"{server_id}_{instance}"


def split_hyperion_unique_id(unique_id) -> Tuple[str, int]:
    """Split a unique_id for a Hyperion instance."""
    try:
        server_id, instance = unique_id.rsplit("_", 1)
        return server_id, int(instance)
    except ValueError:
        return None


async def async_create_connect_client(
    host: str,
    port: int,
    instance: int = hyperion_const.DEFAULT_INSTANCE,
    token: str = None,
):
    """Create and connect a Hyperion Client."""
    hyperion_client = client.HyperionClient(host, port, token=token, instance=instance)

    if not await hyperion_client.async_client_connect():
        return None
    return hyperion_client


async def async_setup(hass: HomeAssistant, config: Dict[str, Any]) -> bool:
    """Set up Hyperion component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Hyperion from a config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    token = config_entry.data.get(CONF_TOKEN)

    hyperion_client = await async_create_connect_client(host, port, token=token)
    if not hyperion_client:
        raise ConfigEntryNotReady

    hyperion_client.set_callbacks(
        {
            f"{hyperion_const.KEY_INSTANCE}-{hyperion_const.KEY_UPDATE}": lambda json: (
                async_dispatcher_send(
                    hass,
                    SIGNAL_INSTANCES_UPDATED.format(config_entry.entry_id),
                    json,
                )
            )
        }
    )

    hass.data[DOMAIN][config_entry.entry_id] = {
        CONF_ROOT_CLIENT: hyperion_client,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok and config_entry.entry_id in hass.data[DOMAIN]:
        config_data = hass.data[DOMAIN].pop(config_entry.entry_id)
        root_client = config_data[CONF_ROOT_CLIENT]
        await root_client.async_client_connect()
    return unload_ok
