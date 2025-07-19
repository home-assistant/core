"""The Hyperion component."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
import logging
from typing import Any, cast

from awesomeversion import AwesomeVersion
from hyperion import client, const as hyperion_const

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    HYPERION_RELEASES_URL,
    HYPERION_VERSION_WARN_CUTOFF,
    SIGNAL_INSTANCE_ADD,
    SIGNAL_INSTANCE_REMOVE,
)

PLATFORMS = [Platform.CAMERA, Platform.LIGHT, Platform.SENSOR, Platform.SWITCH]

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

type HyperionConfigEntry = ConfigEntry[HyperionData]


@dataclass
class HyperionData:
    """Hyperion runtime data."""

    root_client: client.HyperionClient
    instance_clients: dict[int, client.HyperionClient]


def get_hyperion_unique_id(server_id: str, instance: int, name: str) -> str:
    """Get a unique_id for a Hyperion instance."""
    return f"{server_id}_{instance}_{name}"


def get_hyperion_device_id(server_id: str, instance: int) -> str:
    """Get an id for a Hyperion device/instance."""
    return f"{server_id}_{instance}"


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


@callback
def listen_for_instance_updates(
    hass: HomeAssistant,
    entry: HyperionConfigEntry,
    add_func: Callable[[int, str], None],
    remove_func: Callable[[int], None],
) -> None:
    """Listen for instance additions/removals."""

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_INSTANCE_ADD.format(entry.entry_id),
            add_func,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            SIGNAL_INSTANCE_REMOVE.format(entry.entry_id),
            remove_func,
        )
    )


async def async_setup_entry(hass: HomeAssistant, entry: HyperionConfigEntry) -> bool:
    """Set up Hyperion from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    token = entry.data.get(CONF_TOKEN)

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
                    (
                        "Using a Hyperion server version < %s is not recommended --"
                        " some features may be unavailable or may not function"
                        " correctly. Please consider upgrading: %s"
                    ),
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
        raise ConfigEntryAuthFailed

    # Client login doesn't work? => Reauth.
    if not await hyperion_client.async_client_login():
        await hyperion_client.async_client_disconnect()
        raise ConfigEntryAuthFailed

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
    entry.runtime_data = HyperionData(
        root_client=hyperion_client,
        instance_clients={},
    )

    async def async_instances_to_clients(response: dict[str, Any]) -> None:
        """Convert instances to Hyperion clients."""
        if not response or hyperion_const.KEY_DATA not in response:
            return
        await async_instances_to_clients_raw(response[hyperion_const.KEY_DATA])

    async def async_instances_to_clients_raw(instances: list[dict[str, Any]]) -> None:
        """Convert instances to Hyperion clients."""
        device_registry = dr.async_get(hass)
        running_instances: set[int] = set()
        stopped_instances: set[int] = set()
        existing_instances = entry.runtime_data.instance_clients
        server_id = cast(str, entry.unique_id)

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
                SIGNAL_INSTANCE_ADD.format(entry.entry_id),
                instance_num,
                instance_name,
            )

        # Remove entities that are not running instances on Hyperion.
        for instance_num in set(existing_instances) - running_instances:
            del existing_instances[instance_num]
            async_dispatcher_send(
                hass, SIGNAL_INSTANCE_REMOVE.format(entry.entry_id), instance_num
            )

        # Ensure every device associated with this config entry is still in the list of
        # motionEye cameras, otherwise remove the device (and thus entities).
        known_devices = {
            get_hyperion_device_id(server_id, instance_num)
            for instance_num in running_instances | stopped_instances
        }
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            for kind, key in device_entry.identifiers:
                if kind == DOMAIN and key in known_devices:
                    break
            else:
                device_registry.async_remove_device(device_entry.id)

    hyperion_client.set_callbacks(
        {
            f"{hyperion_const.KEY_INSTANCE}-{hyperion_const.KEY_UPDATE}": async_instances_to_clients,
        }
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    assert hyperion_client
    if hyperion_client.instances is not None:
        await async_instances_to_clients_raw(hyperion_client.instances)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    return True


async def _async_entry_updated(hass: HomeAssistant, entry: HyperionConfigEntry) -> None:
    """Handle entry updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HyperionConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Disconnect the shared instance clients.
        await asyncio.gather(
            *(
                inst.async_client_disconnect()
                for inst in entry.runtime_data.instance_clients.values()
            )
        )

        # Disconnect the root client.
        root_client = entry.runtime_data.root_client
        await root_client.async_client_disconnect()
    return unload_ok
