"""The Minecraft Server integration."""

from datetime import timedelta
import logging

from mcstatus.server import MinecraftServer as MCStatus

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_UPDATE_INTERVAL, DOMAIN, MANUFACTURER, SIGNAL_NAME_PREFIX

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Minecraft Server component."""
    return True


async def async_setup_entry(hass, config_entry):
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


async def async_unload_entry(hass, config_entry):
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
    _COLOR_CODES = [
        "§0",
        "§1",
        "§2",
        "§3",
        "§4",
        "§5",
        "§6",
        "§7",
        "§8",
        "§9",
        "§a",
        "§b",
        "§c",
        "§d",
        "§e",
        "§f",
        "§k",
        "§l",
        "§m",
        "§n",
        "§o",
        "§r",
    ]
    _RETRIES_PING = 3
    _RETRIES_STATUS = 3

    def __init__(self, hass, unique_id, config_data, skip_periodic_update=False):
        """Initialize server instance."""
        self._hass = hass
        self._unique_id = unique_id

        # Server data
        self._name = config_data[CONF_NAME]
        self._host = config_data[CONF_HOST]
        self._port = config_data[CONF_PORT]
        self._update_interval = config_data[CONF_UPDATE_INTERVAL]
        self._server_online = False

        _LOGGER.debug(
            "Initializing '%s' (host='%s', port=%s, update_interval=%s)...",
            self._name,
            self._host,
            self._port,
            self._update_interval,
        )

        # 3rd party library instance
        self._mcstatus = MCStatus(self._host, self._port)

        # Data provided by 3rd party library
        self._description = STATE_UNKNOWN
        self._version = STATE_UNKNOWN
        self._protocol_version = STATE_UNKNOWN
        self._latency = STATE_UNKNOWN
        self._players_online = STATE_UNKNOWN
        self._players_max = STATE_UNKNOWN
        self._players_list = STATE_UNAVAILABLE

        # Dispatcher signal name
        self._signal_name = SIGNAL_NAME_PREFIX + self._unique_id

        # Periodically update status.
        if skip_periodic_update:
            _LOGGER.debug("Got request to skip setup of periodic update.")
        else:
            self._stop_track_time_interval = async_track_time_interval(
                self._hass, self.async_update, timedelta(seconds=self._update_interval),
            )

    @property
    def name(self):
        """Return server name."""
        return self._name

    @property
    def unique_id(self):
        """Return server unique ID."""
        return self._unique_id

    @property
    def host(self):
        """Return server host."""
        return self._host

    @property
    def port(self):
        """Return server port."""
        return self._port

    @property
    def signal_name(self):
        """Return dispatcher signal name."""
        return self._signal_name

    @property
    def description(self):
        """Return server description."""
        return self._description

    @property
    def version(self):
        """Return server version."""
        return self._version

    @property
    def protocol_version(self):
        """Return server protocol version."""
        return self._protocol_version

    @property
    def latency_time(self):
        """Return server latency time."""
        return self._latency

    @property
    def players_online(self):
        """Return online players on server."""
        return self._players_online

    @property
    def players_max(self):
        """Return maximum number of players on server."""
        return self._players_max

    @property
    def players_list(self):
        """Return players list on server."""
        return self._players_list

    @property
    def online(self):
        """Return server connection status."""
        return self._server_online

    def stop_periodic_update(self):
        """Stop periodic execution of update method."""
        if self._stop_track_time_interval is not None:
            self._stop_track_time_interval()
        else:
            _LOGGER.debug(
                "Listener was not started, stopping of periodic update skipped."
            )

    async def async_check_connection(self):
        """Check server connection using a 'ping' request and store result."""
        try:
            await self._hass.async_add_executor_job(
                self._mcstatus.ping, self._RETRIES_PING
            )
            self._server_online = True
        except IOError as error:
            _LOGGER.debug("Error occured while trying to ping the server (%s).", error)
            self._server_online = False

    async def async_update(self, now=None):
        """Get server data from 3rd party library and update properties."""
        # Check connection status.
        server_online_old = self.online
        await self.async_check_connection()
        server_online = self.online

        # Inform user once about connection state changes if necessary.
        if (server_online_old is True) and (server_online is False):
            _LOGGER.warning("Connection to server lost.")
        elif (server_online_old is False) and (server_online is True):
            _LOGGER.info("Connection to server (re-)established.")

        # Try to update the server data if server is online.
        if server_online:
            try:
                await self._async_status_request()
            except IOError as error:
                _LOGGER.debug(
                    "Error occured while trying to update the server data (%s).", error
                )
        else:
            # Set all properties except description and version information to
            # unknown until server connection is established again.
            self._players_online = STATE_UNKNOWN
            self._players_max = STATE_UNKNOWN
            self._players_list = STATE_UNKNOWN
            self._latency = STATE_UNKNOWN

        # Notify sensors about new data.
        async_dispatcher_send(self._hass, self._signal_name)

    async def _async_status_request(self):
        """Request server status and update properties."""
        try:
            status_response = await self._hass.async_add_executor_job(
                self._mcstatus.status, self._RETRIES_STATUS
            )
        except IOError:
            _LOGGER.debug("Error while requesting server status (IOError).")
            raise IOError
        else:
            self._description = status_response.description["text"]

            # Remove color codes.
            for color_code in self._COLOR_CODES:
                self._description = self._description.replace(color_code, "")

            # Remove newlines.
            self._description = self._description.replace("\n", " ")

            # Limit description length to 255.
            if len(self._description) > 255:
                self._description = self._description[:255]
                _LOGGER.debug("Description length > 255 (truncated).")

            self._version = status_response.version.name
            self._protocol_version = status_response.version.protocol
            self._players_online = status_response.players.online
            self._players_max = status_response.players.max
            self._latency = status_response.latency

            if status_response.players.sample is None:
                self._players_list = "[]"
            else:
                self._players_list = "["

                for player in status_response.players.sample:
                    self._players_list += player.name + ", "

                # Remove last seperator ", " and add end bracket.
                self._players_list = self._players_list[:-2] + "]"

                # Limit players list length to 255.
                if len(self._players_list) > 255:
                    self._players_list = self._players_list[:-4] + "...]"
                    _LOGGER.debug("Players list length > 255 (truncated).")


class MinecraftServerEntity(Entity):
    """Representation of a Minecraft Server base entity."""

    def __init__(self, hass, server, name, unit, icon):
        """Initialize base entity."""
        self._server = server
        self._hass = hass
        self._state = None
        self._name = server.name + " " + name
        self._sensor_name = name
        self._unit = unit
        self._icon = icon
        self._unique_id = f"{self._server.unique_id}-{self._sensor_name}"
        self._device_info = {
            "identifiers": {(DOMAIN, self._server.unique_id)},
            "name": self._server.name,
            "manufacturer": MANUFACTURER,
            "model": f"Minecraft Server ({self._server.version})",
            "sw_version": self._server.protocol_version,
        }
        self._disconnect_dispatcher = None

    @property
    def name(self):
        """Return sensor name."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return self._device_info

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return sensor measurement unit."""
        return self._unit

    @property
    def icon(self):
        """Return sensor icon."""
        return self._icon

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    async def async_update(self):
        """Fetch sensor data from the server."""
        raise NotImplementedError()

    async def async_added_to_hass(self):
        """Connect dispatcher to signal from server."""
        self._disconnect_dispatcher = async_dispatcher_connect(
            self._hass, self._server.signal_name, self._async_update_callback
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher before removal."""
        self._disconnect_dispatcher()

    async def _async_update_callback(self):
        """Triggers update of properties after receiving signal from server."""
        self.async_schedule_update_ha_state(force_refresh=True)
