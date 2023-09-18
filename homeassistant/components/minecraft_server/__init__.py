"""The Minecraft Server integration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

import aiodns
from mcstatus.server import JavaServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    KEY_LATENCY,
    KEY_MOTD,
    SCAN_INTERVAL,
    SIGNAL_NAME_PREFIX,
    SRV_RECORD_PREFIX,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minecraft Server from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    # Create and store server instance.
    config_entry_id = entry.entry_id
    _LOGGER.debug(
        "Creating server instance for '%s' (%s)",
        entry.data[CONF_NAME],
        entry.data[CONF_HOST],
    )
    server = MinecraftServer(hass, config_entry_id, entry.data)
    domain_data[config_entry_id] = server
    await server.async_update()
    server.start_periodic_update()

    # Set up platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Minecraft Server config entry."""
    config_entry_id = config_entry.entry_id
    server = hass.data[DOMAIN][config_entry_id]

    # Unload platforms.
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # Clean up.
    server.stop_periodic_update()
    hass.data[DOMAIN].pop(config_entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to a new format."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    # 1 --> 2: Use config entry ID as base for unique IDs.
    if config_entry.version == 1:
        old_unique_id = config_entry.unique_id
        assert old_unique_id
        config_entry_id = config_entry.entry_id

        # Migrate config entry.
        _LOGGER.debug("Migrating config entry. Resetting unique ID: %s", old_unique_id)
        config_entry.unique_id = None
        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry)

        # Migrate device.
        await _async_migrate_device_identifiers(hass, config_entry, old_unique_id)

        # Migrate entities.
        await er.async_migrate_entries(hass, config_entry_id, _migrate_entity_unique_id)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True


async def _async_migrate_device_identifiers(
    hass: HomeAssistant, config_entry: ConfigEntry, old_unique_id: str | None
) -> None:
    """Migrate the device identifiers to the new format."""
    device_registry = dr.async_get(hass)
    device_entry_found = False
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for identifier in device_entry.identifiers:
            if identifier[1] == old_unique_id:
                # Device found in registry. Update identifiers.
                new_identifiers = {
                    (
                        DOMAIN,
                        config_entry.entry_id,
                    )
                }
                _LOGGER.debug(
                    "Migrating device identifiers from %s to %s",
                    device_entry.identifiers,
                    new_identifiers,
                )
                device_registry.async_update_device(
                    device_id=device_entry.id, new_identifiers=new_identifiers
                )
                # Device entry found. Leave inner for loop.
                device_entry_found = True
                break

        # Leave outer for loop if device entry is already found.
        if device_entry_found:
            break


@callback
def _migrate_entity_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any]:
    """Migrate the unique ID of an entity to the new format."""

    # Different variants of unique IDs are available in version 1:
    # 1) SRV record: '<host>-srv-<entity_type>'
    # 2) Host & port: '<host>-<port>-<entity_type>'
    # 3) IP address & port: '<mac_address>-<port>-<entity_type>'
    unique_id_pieces = entity_entry.unique_id.split("-")
    entity_type = unique_id_pieces[2]

    # Handle bug in version 1: Entity type names were used instead of
    # keys (e.g. "Protocol Version" instead of "protocol_version").
    new_entity_type = entity_type.lower()
    new_entity_type = new_entity_type.replace(" ", "_")

    # Special case 'MOTD': Name and key differs.
    if new_entity_type == "world_message":
        new_entity_type = KEY_MOTD

    # Special case 'latency_time': Renamed to 'latency'.
    if new_entity_type == "latency_time":
        new_entity_type = KEY_LATENCY

    new_unique_id = f"{entity_entry.config_entry_id}-{new_entity_type}"
    _LOGGER.debug(
        "Migrating entity unique ID from %s to %s",
        entity_entry.unique_id,
        new_unique_id,
    )

    return {"new_unique_id": new_unique_id}


@dataclass
class MinecraftServerData:
    """Representation of Minecraft server data."""

    latency: float | None = None
    motd: str | None = None
    players_max: int | None = None
    players_online: int | None = None
    players_list: list[str] | None = None
    protocol_version: int | None = None
    version: str | None = None


class MinecraftServer:
    """Representation of a Minecraft server."""

    def __init__(
        self, hass: HomeAssistant, unique_id: str, config_data: Mapping[str, Any]
    ) -> None:
        """Initialize server instance."""
        self._hass = hass

        # Server data
        self.unique_id = unique_id
        self.name = config_data[CONF_NAME]
        self.host = config_data[CONF_HOST]
        self.port = config_data[CONF_PORT]
        self.online = False
        self._last_status_request_failed = False
        self.srv_record_checked = False

        # 3rd party library instance
        self._server = JavaServer(self.host, self.port)

        # Data provided by 3rd party library
        self.data: MinecraftServerData = MinecraftServerData()

        # Dispatcher signal name
        self.signal_name = f"{SIGNAL_NAME_PREFIX}_{self.unique_id}"

        # Callback for stopping periodic update.
        self._stop_periodic_update: CALLBACK_TYPE | None = None

    def start_periodic_update(self) -> None:
        """Start periodic execution of update method."""
        self._stop_periodic_update = async_track_time_interval(
            self._hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

    def stop_periodic_update(self) -> None:
        """Stop periodic execution of update method."""
        if self._stop_periodic_update:
            self._stop_periodic_update()

    async def async_check_connection(self) -> None:
        """Check server connection using a 'status' request and store connection status."""
        # Check if host is a valid SRV record, if not already done.
        if not self.srv_record_checked:
            self.srv_record_checked = True
            srv_record = await self._async_check_srv_record(self.host)
            if srv_record is not None:
                _LOGGER.debug(
                    "'%s' is a valid Minecraft SRV record ('%s:%s')",
                    self.host,
                    srv_record[CONF_HOST],
                    srv_record[CONF_PORT],
                )
                # Overwrite host, port and 3rd party library instance
                # with data extracted out of SRV record.
                self.host = srv_record[CONF_HOST]
                self.port = srv_record[CONF_PORT]
                self._server = JavaServer(self.host, self.port)

        # Ping the server with a status request.
        try:
            await self._server.async_status()
            self.online = True
        except OSError as error:
            _LOGGER.debug(
                (
                    "Error occurred while trying to check the connection to '%s:%s' -"
                    " OSError: %s"
                ),
                self.host,
                self.port,
                error,
            )
            self.online = False

    async def _async_check_srv_record(self, host: str) -> dict[str, Any] | None:
        """Check if the given host is a valid Minecraft SRV record."""
        srv_record = None
        srv_query = None

        try:
            srv_query = await aiodns.DNSResolver().query(
                host=f"{SRV_RECORD_PREFIX}.{host}", qtype="SRV"
            )
        except aiodns.error.DNSError:
            # 'host' is not a SRV record.
            pass
        else:
            # 'host' is a valid SRV record, extract the data.
            srv_record = {
                CONF_HOST: srv_query[0].host,
                CONF_PORT: srv_query[0].port,
            }

        return srv_record

    async def async_update(self, now: datetime | None = None) -> None:
        """Get server data from 3rd party library and update properties."""
        # Check connection status.
        server_online_old = self.online
        await self.async_check_connection()
        server_online = self.online

        # Inform user once about connection state changes if necessary.
        if server_online_old and not server_online:
            _LOGGER.warning("Connection to '%s:%s' lost", self.host, self.port)
        elif not server_online_old and server_online:
            _LOGGER.info("Connection to '%s:%s' (re-)established", self.host, self.port)

        # Update the server properties if server is online.
        if server_online:
            await self._async_status_request()

        # Notify sensors about new data.
        async_dispatcher_send(self._hass, self.signal_name)

    async def _async_status_request(self) -> None:
        """Request server status and update properties."""
        try:
            status_response = await self._server.async_status()

            # Got answer to request, update properties.
            self.data.version = status_response.version.name
            self.data.protocol_version = status_response.version.protocol
            self.data.players_online = status_response.players.online
            self.data.players_max = status_response.players.max
            self.data.latency = status_response.latency
            self.data.motd = status_response.motd.to_plain()

            self.data.players_list = []
            if status_response.players.sample is not None:
                for player in status_response.players.sample:
                    self.data.players_list.append(player.name)
                self.data.players_list.sort()

            # Inform user once about successful update if necessary.
            if self._last_status_request_failed:
                _LOGGER.info(
                    "Updating the properties of '%s:%s' succeeded again",
                    self.host,
                    self.port,
                )
            self._last_status_request_failed = False
        except OSError as error:
            # No answer to request, set all properties to unknown.
            self.data.version = None
            self.data.protocol_version = None
            self.data.players_online = None
            self.data.players_max = None
            self.data.latency = None
            self.data.players_list = None
            self.data.motd = None

            # Inform user once about failed update if necessary.
            if not self._last_status_request_failed:
                _LOGGER.warning(
                    "Updating the properties of '%s:%s' failed - OSError: %s",
                    self.host,
                    self.port,
                    error,
                )
            self._last_status_request_failed = True
