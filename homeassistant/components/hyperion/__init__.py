"""The Hyperion component."""

import asyncio
import logging
from typing import Any, Optional

from hyperion import client, const as hyperion_const
from pkg_resources import parse_version

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_ON_UNLOAD,
    CONF_ROOT_CLIENT,
    DOMAIN,
    HYPERION_RELEASES_URL,
    HYPERION_VERSION_WARN_CUTOFF,
    SIGNAL_INSTANCES_UPDATED,
)

PLATFORMS = [LIGHT_DOMAIN]

_LOGGER = logging.getLogger(__name__)

# Unique ID
# =========
# A config entry represents a connection to a single Hyperion server. The config entry
# unique_id is the server id returned from the Hyperion instance (a unique ID per
# server).
#
# Each server connection may create multiple entities. The unique_id for each entity is
# <server id>_<instance #>_<name>, where <server_id> will be the unique_id on the
# relevant config entry (as above), <instance #> will be the server instance # and
# <name> will be a unique identifying type name for each entity associated with this
# server/instance (e.g. "hyperion_light").
#
# The get_hyperion_unique_id method will create a per-entity unique id when given the
# server id, an instance number and a name.

# hass.data format
# ================
#
# hass.data[DOMAIN] = {
#     <config_entry.entry_id>: {
#         "ROOT_CLIENT": <Hyperion Client>,
#         "ON_UNLOAD": [<callable>, ...],
#     }
# }


def get_hyperion_unique_id(server_id: str, instance: int, name: str) -> str:
    """Get a unique_id for a Hyperion instance."""
    return f"{server_id}_{instance}_{name}"


def create_hyperion_client(
    *args: Any,
    **kwargs: Any,
) -> client.HyperionClient:
    """Create a Hyperion Client."""
    return client.HyperionClient(*args, **kwargs)


async def async_create_connect_hyperion_client(
    *args: Any,
    **kwargs: Any,
) -> Optional[client.HyperionClient]:
    """Create and connect a Hyperion Client."""
    hyperion_client = create_hyperion_client(*args, **kwargs)

    if not await hyperion_client.async_client_connect():
        return None
    return hyperion_client


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Hyperion component."""
    hass.data[DOMAIN] = {}
    return True


async def _create_reauth_flow(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> None:
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_REAUTH}, data=config_entry.data
        )
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Hyperion from a config entry."""
    host = config_entry.data[CONF_HOST]
    port = config_entry.data[CONF_PORT]
    token = config_entry.data.get(CONF_TOKEN)

    hyperion_client = await async_create_connect_hyperion_client(
        host, port, token=token, raw_connection=True
    )

    # Client won't connect? => Not ready.
    if not hyperion_client:
        raise ConfigEntryNotReady
    version = await hyperion_client.async_sysinfo_version()
    if version is not None:
        try:
            if parse_version(version) < parse_version(HYPERION_VERSION_WARN_CUTOFF):
                _LOGGER.warning(
                    "Using a Hyperion server version < %s is not recommended -- "
                    "some features may be unavailable or may not function correctly. "
                    "Please consider upgrading: %s",
                    HYPERION_VERSION_WARN_CUTOFF,
                    HYPERION_RELEASES_URL,
                )
        except ValueError:
            pass

    # Client needs authentication, but no token provided? => Reauth.
    auth_resp = await hyperion_client.async_is_auth_required()
    if (
        auth_resp is not None
        and client.ResponseOK(auth_resp)
        and auth_resp.get(hyperion_const.KEY_INFO, {}).get(
            hyperion_const.KEY_REQUIRED, False
        )
        and token is None
    ):
        await _create_reauth_flow(hass, config_entry)
        return False

    # Client login doesn't work? => Reauth.
    if not await hyperion_client.async_client_login():
        await _create_reauth_flow(hass, config_entry)
        return False

    # Cannot switch instance or cannot load state? => Not ready.
    if (
        not await hyperion_client.async_client_switch_instance()
        or not client.ServerInfoResponseOK(await hyperion_client.async_get_serverinfo())
    ):
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
        CONF_ON_UNLOAD: [],
    }

    # Must only listen for option updates after the setup is complete, as otherwise
    # the YAML->ConfigEntry migration code triggers an options update, which causes a
    # reload -- which clashes with the initial load (causing entity_id / unique_id
    # clashes).
    async def setup_then_listen() -> None:
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(config_entry, component)
                for component in PLATFORMS
            ]
        )
        hass.data[DOMAIN][config_entry.entry_id][CONF_ON_UNLOAD].append(
            config_entry.add_update_listener(_async_entry_updated)
        )

    hass.async_create_task(setup_then_listen())
    return True


async def _async_entry_updated(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> None:
    """Handle entry updates."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
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
        for func in config_data[CONF_ON_UNLOAD]:
            func()
        root_client = config_data[CONF_ROOT_CLIENT]
        await root_client.async_client_disconnect()
    return unload_ok
