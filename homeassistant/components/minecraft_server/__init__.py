"""The Minecraft Server integration."""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List

from mcstatus.server import MinecraftServer as MCStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util.dt import utcnow

from .const import DOMAIN, MANUFACTURER, SIGNAL_NAME_PREFIX

PLATFORMS = ["binary_sensor", "sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Minecraft Server component."""
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry) -> bool:
    """Set up Minecraft Server from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create and store server instance.
    unique_id = config_entry.unique_id
    server = MinecraftServer(hass, unique_id, config_entry.data)
    hass.data[DOMAIN][unique_id] = server
    await server.async_update()

    # Set up platform(s).
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry
) -> bool:
    """Unload Minecraft Server config entry."""
    unique_id = config_entry.unique_id
    server = hass.data[DOMAIN][unique_id]

    # Unload platforms.
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, platform)

    # Clean up.
    server.stop_periodic_update()
    hass.data[DOMAIN].pop(unique_id)

    return True


class MinecraftServer:
    """Representation of a Minecraft server."""

    # Private constants
    _RETRIES_PING = 3
    _RETRIES_STATUS = 3

    def __init__(
        self, hass: HomeAssistantType, unique_id: str, config_data: ConfigType
    ) -> None:
        """Initialize server instance."""
        self._hass = hass
        self._unique_id = unique_id

        # Server data
        self._name = config_data[CONF_NAME]
        self._host = config_data[CONF_HOST]
        self._port = config_data[CONF_PORT]
        self._scan_interval = config_data[CONF_SCAN_INTERVAL]
        self._server_online = False
        self._stop_periodic_update = None

        _LOGGER.debug(
            "Initializing '%s' (host='%s', port=%s, scan_interval=%s)",
            self._name,
            self._host,
            self._port,
            self._scan_interval,
        )

        # 3rd party library instance
        self._mcstatus = MCStatus(self._host, self._port)

        # Data provided by 3rd party library
        self._description = None
        self._version = None
        self._protocol_version = None
        self._latency = None
        self._players_online = None
        self._players_max = None
        self._players_list = None

        # Dispatcher signal name
        self._signal_name = SIGNAL_NAME_PREFIX + self._unique_id

    @property
    def name(self) -> str:
        """Return server name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return server unique ID."""
        return self._unique_id

    @property
    def host(self) -> str:
        """Return server host."""
        return self._host

    @property
    def port(self) -> int:
        """Return server port."""
        return self._port

    @property
    def signal_name(self) -> str:
        """Return dispatcher signal name."""
        return self._signal_name

    @property
    def description(self) -> str:
        """Return server description."""
        return self._description

    @property
    def version(self) -> str:
        """Return server version."""
        return self._version

    @property
    def protocol_version(self) -> int:
        """Return server protocol version."""
        return self._protocol_version

    @property
    def latency_time(self) -> int:
        """Return server latency time."""
        return self._latency

    @property
    def players_online(self) -> int:
        """Return online players on server."""
        return self._players_online

    @property
    def players_max(self) -> int:
        """Return maximum number of players on server."""
        return self._players_max

    @property
    def players_list(self) -> List[str]:
        """Return players list on server."""
        return self._players_list

    @property
    def online(self) -> bool:
        """Return server connection status."""
        return self._server_online

    def stop_periodic_update(self) -> None:
        """Stop periodic execution of update method."""
        if self._stop_periodic_update is not None:
            self._stop_periodic_update()
        else:
            _LOGGER.debug(
                "Listener was not started, stopping of periodic update skipped"
            )

    async def async_check_connection(self) -> None:
        """Check server connection using a 'ping' request and store result."""
        try:
            await self._hass.async_add_executor_job(
                self._mcstatus.ping, self._RETRIES_PING
            )
            self._server_online = True
        except IOError as error:
            _LOGGER.debug("Error occured while trying to ping the server: %s", error)
            self._server_online = False

    async def async_update(self, now: datetime = None) -> None:
        """Get server data from 3rd party library and update properties."""
        # Check connection status.
        server_online_old = self.online
        await self.async_check_connection()
        server_online = self.online

        # Inform user once about connection state changes if necessary.
        if (server_online_old is True) and (server_online is False):
            _LOGGER.warning("Connection to server lost")
        elif (server_online_old is False) and (server_online is True):
            _LOGGER.info("Connection to server (re-)established")

        # Try to update the server data if server is online.
        if server_online:
            try:
                await self._async_status_request()
            except IOError as error:
                _LOGGER.debug(
                    "Error occured while trying to update the server data: %s", error
                )
        else:
            # Set all properties except description and version information to
            # unknown until server connection is established again.
            self._players_online = None
            self._players_max = None
            self._players_list = None
            self._latency = None

        # Notify sensors about new data.
        async_dispatcher_send(self._hass, self._signal_name)

        # Periodically update status.
        self._stop_periodic_update = async_track_point_in_utc_time(
            self._hass,
            self.async_update,
            utcnow() + timedelta(seconds=self._scan_interval),
        )

    async def _async_status_request(self) -> None:
        """Request server status and update properties."""
        try:
            status_response = await self._hass.async_add_executor_job(
                self._mcstatus.status, self._RETRIES_STATUS
            )
        except IOError:
            _LOGGER.debug("Error while requesting server status: IOError")
            raise IOError
        else:
            self._description = status_response.description["text"]
            self._version = status_response.version.name
            self._protocol_version = status_response.version.protocol
            self._players_online = status_response.players.online
            self._players_max = status_response.players.max
            self._latency = status_response.latency
            self._players_list = []
            if status_response.players.sample is not None:
                for player in status_response.players.sample:
                    self._players_list.append(player.name)


class MinecraftServerEntity(Entity):
    """Representation of a Minecraft Server base entity."""

    def __init__(
        self,
        hass: HomeAssistantType,
        server: MinecraftServer,
        type_name: str,
        icon: str,
        device_class: str,
    ) -> None:
        """Initialize base entity."""
        self._server = server
        self._hass = hass
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
    def device_info(self) -> Dict[str, Any]:
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
            self._hass, self._server.signal_name, self._update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher before removal."""
        self._disconnect_dispatcher()

    @callback
    def _update_callback(self) -> None:
        """Triggers update of properties after receiving signal from server."""
        self.async_schedule_update_ha_state(force_refresh=True)
