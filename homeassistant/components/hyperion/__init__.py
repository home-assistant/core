"""The Hyperion component."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import Any, Callable, cast

from awesomeversion import AwesomeVersion
from hyperion import client, const as hyperion_const

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE, CONF_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    CONF_INSTANCE_CLIENTS,
    CONF_ON_UNLOAD,
    CONF_ROOT_CLIENT,
    DEFAULT_NAME,
    DOMAIN,
    HYPERION_RELEASES_URL,
    HYPERION_VERSION_WARN_CUTOFF,
    SIGNAL_INSTANCE_ADD,
    SIGNAL_INSTANCE_REMOVE,
)

PLATFORMS = [LIGHT_DOMAIN, SWITCH_DOMAIN]

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


def split_hyperion_unique_id(unique_id: str) -> tuple[str, int, str] | None:
    """Split a unique_id into a (server_id, instance, type) tuple."""
    data = tuple(unique_id.split("_", 2))
    if len(data) != 3:
        return None
    try:
        return (data[0], int(data[1]), data[2])
    except ValueError:
        return None


def create_hyperion_client(
    *args: Any,
    **kwargs: Any,
) -> client.HyperionClient:
    """Create a Hyperion Client."""
    return client.HyperionClient(*args, **kwargs)


async def async_create_connect_hyperion_client(
    *args: Any,
    **kwargs: Any,
) -> client.HyperionClient | None:
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


@callback
def listen_for_instance_updates(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    add_func: Callable,
    remove_func: Callable,
) -> None:
    """Listen for instance additions/removals."""

    hass.data[DOMAIN][config_entry.entry_id][CONF_ON_UNLOAD].extend(
        [
            async_dispatcher_connect(
                hass,
                SIGNAL_INSTANCE_ADD.format(config_entry.entry_id),
                add_func,
            ),
            async_dispatcher_connect(
                hass,
                SIGNAL_INSTANCE_REMOVE.format(config_entry.entry_id),
                remove_func,
            ),
        ]
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
        with suppress(ValueError):
            if AwesomeVersion(version) < AwesomeVersion(HYPERION_VERSION_WARN_CUTOFF):
                _LOGGER.warning(
                    "Using a Hyperion server version < %s is not recommended -- "
                    "some features may be unavailable or may not function correctly. "
                    "Please consider upgrading: %s",
                    HYPERION_VERSION_WARN_CUTOFF,
                    HYPERION_RELEASES_URL,
                )

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
        await hyperion_client.async_client_disconnect()
        await _create_reauth_flow(hass, config_entry)
        return False

    # Client login doesn't work? => Reauth.
    if not await hyperion_client.async_client_login():
        await hyperion_client.async_client_disconnect()
        await _create_reauth_flow(hass, config_entry)
        return False

    # Cannot switch instance or cannot load state? => Not ready.
    if (
        not await hyperion_client.async_client_switch_instance()
        or not client.ServerInfoResponseOK(await hyperion_client.async_get_serverinfo())
    ):
        await hyperion_client.async_client_disconnect()
        raise ConfigEntryNotReady

    # We need 1 root client (to manage instances being removed/added) and then 1 client
    # per Hyperion server instance which is shared for all entities associated with
    # that instance.
    hass.data[DOMAIN][config_entry.entry_id] = {
        CONF_ROOT_CLIENT: hyperion_client,
        CONF_INSTANCE_CLIENTS: {},
        CONF_ON_UNLOAD: [],
    }

    async def async_instances_to_clients(response: dict[str, Any]) -> None:
        """Convert instances to Hyperion clients."""
        if not response or hyperion_const.KEY_DATA not in response:
            return
        await async_instances_to_clients_raw(response[hyperion_const.KEY_DATA])

    async def async_instances_to_clients_raw(instances: list[dict[str, Any]]) -> None:
        """Convert instances to Hyperion clients."""
        registry = await async_get_registry(hass)
        running_instances: set[int] = set()
        stopped_instances: set[int] = set()
        existing_instances = hass.data[DOMAIN][config_entry.entry_id][
            CONF_INSTANCE_CLIENTS
        ]
        server_id = cast(str, config_entry.unique_id)

        # In practice, an instance can be in 3 states as seen by this function:
        #
        #    * Exists, and is running: Should be present in HASS/registry.
        #    * Exists, but is not running: Cannot add it yet, but entity may have be
        #      registered from a previous time it was running.
        #    * No longer exists at all: Should not be present in HASS/registry.

        # Add instances that are missing.
        for instance in instances:
            instance_num = instance.get(hyperion_const.KEY_INSTANCE)
            if instance_num is None:
                continue
            if not instance.get(hyperion_const.KEY_RUNNING, False):
                stopped_instances.add(instance_num)
                continue
            running_instances.add(instance_num)
            if instance_num in existing_instances:
                continue
            hyperion_client = await async_create_connect_hyperion_client(
                host, port, instance=instance_num, token=token
            )
            if not hyperion_client:
                continue
            existing_instances[instance_num] = hyperion_client
            instance_name = instance.get(hyperion_const.KEY_FRIENDLY_NAME, DEFAULT_NAME)
            async_dispatcher_send(
                hass,
                SIGNAL_INSTANCE_ADD.format(config_entry.entry_id),
                instance_num,
                instance_name,
            )

        # Remove entities that are are not running instances on Hyperion.
        for instance_num in set(existing_instances) - running_instances:
            del existing_instances[instance_num]
            async_dispatcher_send(
                hass, SIGNAL_INSTANCE_REMOVE.format(config_entry.entry_id), instance_num
            )

        # Deregister entities that belong to removed instances.
        for entry in async_entries_for_config_entry(registry, config_entry.entry_id):
            data = split_hyperion_unique_id(entry.unique_id)
            if not data:
                continue
            if data[0] == server_id and (
                data[1] not in running_instances and data[1] not in stopped_instances
            ):
                registry.async_remove(entry.entity_id)

    hyperion_client.set_callbacks(
        {
            f"{hyperion_const.KEY_INSTANCE}-{hyperion_const.KEY_UPDATE}": async_instances_to_clients,
        }
    )

    async def setup_then_listen() -> None:
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
        assert hyperion_client
        if hyperion_client.instances is not None:
            await async_instances_to_clients_raw(hyperion_client.instances)
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
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok and config_entry.entry_id in hass.data[DOMAIN]:
        config_data = hass.data[DOMAIN].pop(config_entry.entry_id)
        for func in config_data[CONF_ON_UNLOAD]:
            func()

        # Disconnect the shared instance clients.
        await asyncio.gather(
            *[
                config_data[CONF_INSTANCE_CLIENTS][
                    instance_num
                ].async_client_disconnect()
                for instance_num in config_data[CONF_INSTANCE_CLIENTS]
            ]
        )

        # Disconnect the root client.
        root_client = config_data[CONF_ROOT_CLIENT]
        await root_client.async_client_disconnect()
    return unload_ok
