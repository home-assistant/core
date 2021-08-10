"""The Minecraft Server integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from mcstatus.server import MinecraftServer as MCStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from . import helpers
from .const import DOMAIN, MANUFACTURER, SCAN_INTERVAL, SIGNAL_NAME_PREFIX

PLATFORMS = ["binary_sensor", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minecraft Server from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    # Create and store server instance.
    unique_id = entry.unique_id
    _LOGGER.debug(
        "Creating server instance for '%s' (%s)",
        entry.data[CONF_NAME],
        entry.data[CONF_HOST],
    )
    server = MinecraftServer(hass, unique_id, entry.data)
    domain_data[unique_id] = server
    await server.async_update()
    server.start_periodic_update()

    # Set up platforms.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Minecraft Server config entry."""
    unique_id = config_entry.unique_id
    server = hass.data[DOMAIN][unique_id]

    # Unload platforms.
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # Clean up.
    server.stop_periodic_update()
    hass.data[DOMAIN].pop(unique_id)

    return unload_ok


class MinecraftServer:
    """Representation of a Minecraft server."""

    # Private constants
    _MAX_RETRIES_STATUS = 3

    def __init__(
        self, hass: HomeAssistant, unique_id: str, config_data: ConfigType
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
        self._mc_status = MCStatus(self.host, self.port)

        # Data provided by 3rd party library
        self.version = None
        self.protocol_version = None
        self.latency_time = None
        self.players_online = None
        self.players_max = None
        self.players_list = None

        # Dispatcher signal name
        self.signal_name = f"{SIGNAL_NAME_PREFIX}_{self.unique_id}"

        # Callback for stopping periodic update.
        self._stop_periodic_update = None

    def start_periodic_update(self) -> None:
        """Start periodic execution of update method."""
        self._stop_periodic_update = async_track_time_interval(
            self._hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

    def stop_periodic_update(self) -> None:
        """Stop periodic execution of update method."""
        self._stop_periodic_update()

    async def async_check_connection(self) -> None:
        """Check server connection using a 'status' request and store connection status."""
        # Check if host is a valid SRV record, if not already done.
        if not self.srv_record_checked:
            self.srv_record_checked = True
            srv_record = await helpers.async_check_srv_record(self._hass, self.host)
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
                self._mc_status = MCStatus(self.host, self.port)

        # Ping the server with a status request.
        try:
            await self._hass.async_add_executor_job(
                self._mc_status.status, self._MAX_RETRIES_STATUS
            )
            self.online = True
        except OSError as error:
            _LOGGER.debug(
                "Error occurred while trying to check the connection to '%s:%s' - OSError: %s",
                self.host,
                self.port,
                error,
            )
            self.online = False

    async def async_update(self, now: datetime = None) -> None:
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
            status_response = await self._hass.async_add_executor_job(
                self._mc_status.status, self._MAX_RETRIES_STATUS
            )

            # Got answer to request, update properties.
            self.version = status_response.version.name
            self.protocol_version = status_response.version.protocol
            self.players_online = status_response.players.online
            self.players_max = status_response.players.max
            self.latency_time = status_response.latency
            self.players_list = []
            if status_response.players.sample is not None:
                for player in status_response.players.sample:
                    self.players_list.append(player.name)
                self.players_list.sort()

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
            self.version = None
            self.protocol_version = None
            self.players_online = None
            self.players_max = None
            self.latency_time = None
            self.players_list = None

            # Inform user once about failed update if necessary.
            if not self._last_status_request_failed:
                _LOGGER.warning(
                    "Updating the properties of '%s:%s' failed - OSError: %s",
                    self.host,
                    self.port,
                    error,
                )
            self._last_status_request_failed = True


class MinecraftServerEntity(Entity):
    """Representation of a Minecraft Server base entity."""

    def __init__(
        self, server: MinecraftServer, type_name: str, icon: str, device_class: str
    ) -> None:
        """Initialize base entity."""
        self._server = server
        self._name = f"{server.name} {type_name}"
        self._icon = icon
        self._unique_id = f"{self._server.unique_id}-{type_name}"
        self._device_info = {
            "identifiers": {(DOMAIN, self._server.unique_id)},
            "name": self._server.name,
            "manufacturer": MANUFACTURER,
            "model": f"Minecraft Server ({self._server.version})",
            "sw_version": self._server.protocol_version,
        }
        self._device_class = device_class
        self._extra_state_attributes = None
        self._disconnect_dispatcher = None

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self._device_info

    @property
    def device_class(self) -> str:
        """Return device class."""
        return self._device_class

    @property
    def icon(self) -> str:
        """Return icon."""
        return self._icon

    @property
    def should_poll(self) -> bool:
        """Disable polling."""
        return False

    async def async_update(self) -> None:
        """Fetch data from the server."""
        raise NotImplementedError()

    async def async_added_to_hass(self) -> None:
        """Connect dispatcher to signal from server."""
        self._disconnect_dispatcher = async_dispatcher_connect(
            self.hass, self._server.signal_name, self._update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher before removal."""
        self._disconnect_dispatcher()

    @callback
    def _update_callback(self) -> None:
        """Triggers update of properties after receiving signal from server."""
        self.async_schedule_update_ha_state(force_refresh=True)
