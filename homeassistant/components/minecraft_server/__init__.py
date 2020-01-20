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

from .const import (
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    NAME_DESCRIPTION,
    NAME_LATENCY_TIME,
    NAME_PLAYERS_LIST,
    NAME_PLAYERS_MAX,
    NAME_PLAYERS_ONLINE,
    NAME_PROTOCOL_VERSION,
    NAME_VERSION,
    SIGNAL_NAME_PREFIX,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Minecraft Server component."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Minecraft Server from a config entry."""
    _LOGGER.debug("Setting up component...")

    if DOMAIN not in hass.data:
        hass.data.setdefault(DOMAIN, {})

    # Create and store server instance.
    server = MinecraftServer(
        hass,
        config_entry.data[CONF_NAME],
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        config_entry.data[CONF_UPDATE_INTERVAL],
    )
    hass.data[DOMAIN][config_entry.data[CONF_NAME]] = server
    await server.async_update(event_time=None)

    # Set up platform(s).
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    _LOGGER.debug("Component setup finished.")

    return True


async def async_unload_entry(hass, config_entry):
    """Unload Minecraft Server config entry."""
    name = config_entry.data[CONF_NAME]
    server = hass.data[DOMAIN][name]

    _LOGGER.debug(
        "Removing of Minecraft Server config entry '%s' requested via UI.", name
    )

    # Unload platforms.
    for platform in PLATFORMS:
        _LOGGER.debug("Unloading platform '%s'...", platform)
        await hass.config_entries.async_forward_entry_unload(config_entry, platform)

    # Clean up.
    _LOGGER.debug("Stopping periodic update...")
    server.stop_periodic_update()
    _LOGGER.debug("Deleting data...")
    hass.data[DOMAIN].pop(name)

    _LOGGER.debug("Unloading finished.")

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

    def __init__(self, hass, name, host, port, update_interval=0):
        """Initialize server instance."""
        _LOGGER.debug("Initializing Minecraft server '%s'...", name)
        _LOGGER.debug(
            "Configuration: host='%s', port=%s, update_interval=%s",
            host,
            port,
            update_interval,
        )

        self._hass = hass

        # Server data
        self._name = name
        self._host = host
        self._port = port
        self._server_online = False

        # 3rd party library instance
        self._mcstatus = MCStatus(host, port)

        # Data provided by 3rd party library
        self._description = STATE_UNKNOWN
        self._version = STATE_UNKNOWN
        self._protocol_version = STATE_UNKNOWN
        self._latency = STATE_UNKNOWN
        self._players_online = STATE_UNKNOWN
        self._players_max = STATE_UNKNOWN
        self._players_list = STATE_UNAVAILABLE
        self._remove_track_time_interval = None

        # Dispatcher signal name
        signal_name_suffix = self._name.replace(" ", "_")
        signal_name_suffix = signal_name_suffix.lower()
        self._signal_name = SIGNAL_NAME_PREFIX + signal_name_suffix

        # Periodically update status.
        if update_interval == 0:
            _LOGGER.debug("Setting up periodic update skipped.")
        else:
            _LOGGER.debug("Setting up periodic update...")
            self._remove_track_time_interval = async_track_time_interval(
                self._hass, self.async_update, timedelta(seconds=update_interval),
            )

    def stop_periodic_update(self):
        """Stop periodic execution of update method."""
        if self._remove_track_time_interval is not None:
            self._remove_track_time_interval()
            _LOGGER.debug("Periodic update stopped.")
        else:
            _LOGGER.debug(
                "Listener was not started, stopping of periodic update skipped."
            )

    def name(self):
        """Return server name."""
        return self._name

    def description(self):
        """Return server description."""
        return self._description

    def version(self):
        """Return server version."""
        return self._version

    def protocol_version(self):
        """Return server protocol version."""
        return self._protocol_version

    def latency_time(self):
        """Return server latency time."""
        return self._latency

    def players_online(self):
        """Return online players on server."""
        return self._players_online

    def players_max(self):
        """Return maximum number of players on server."""
        return self._players_max

    def players_list(self):
        """Return players list on server."""
        return self._players_list

    async def async_check_connection(self):
        """Check server connection using a 'ping' request and store result."""
        ping_response = None
        exception = None

        _LOGGER.debug("Pinging server...")

        try:
            ping_response = await self._hass.async_add_executor_job(
                self._mcstatus.ping, self._RETRIES_PING
            )
        except IOError as error:
            exception = error
            _LOGGER.debug("Error occured while trying to ping the server (%s).", error)
        if (exception is None) and (ping_response is not None):
            self._server_online = True
            _LOGGER.debug("Ping was successful. Server is online.")
        else:
            self._server_online = False
            _LOGGER.debug("Ping failed. Server is unavailable.")

    def online(self):
        """Return server connection status."""
        return self._server_online

    async def async_update(self, event_time):
        """Get server data from 3rd party library and update properties."""
        # Check connection status.
        server_online_old = self.online()
        await self.async_check_connection()
        server_online = self.online()

        # Inform user once about connection state changes if necessary.
        if (server_online_old is True) and (server_online is False):
            _LOGGER.warning("Connection to server lost.")
        elif (server_online_old is False) and (server_online is True):
            _LOGGER.info("Connection to server established.")
        else:
            _LOGGER.debug("Connection status to server didn't change.")

        # Try to update the server data if server is online.
        exception = None
        if server_online:
            try:
                await self._async_status_request()
            except IOError as error:
                exception = error
            if exception is not None:
                _LOGGER.debug(
                    "Error occured while trying to update the server data (%s).",
                    exception,
                )

        # Either connection to server lost or error occured while requesting data?
        if (not server_online) or (exception is not None):
            # Set all properties to unknown until server connection is established again.
            self._description = STATE_UNKNOWN
            self._version = STATE_UNKNOWN
            self._protocol_version = STATE_UNKNOWN
            self._players_online = STATE_UNKNOWN
            self._players_max = STATE_UNKNOWN
            self._players_list = STATE_UNKNOWN
            self._latency = STATE_UNKNOWN

        # Print debug data.
        self._print_data()

        # Send notification to sensors.
        _LOGGER.debug("Sending signal '%s'.", self._signal_name)
        await self._async_notify()

    async def _async_notify(self):
        """Notify all sensor platforms about new data."""
        async_dispatcher_send(self._hass, self._signal_name)

    async def _async_status_request(self):
        """Request server status and update properties."""
        _LOGGER.debug("Requesting status information...")

        status_response = None
        try:
            status_response = await self._hass.async_add_executor_job(
                self._mcstatus.status, self._RETRIES_STATUS
            )
        except IOError:
            raise IOError

        if status_response is not None:
            _LOGGER.debug("Got status response. Updating properties...")

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

    def _print_data(self):
        """Print properties."""
        _LOGGER.debug(
            """Properties of '%s' (%s:%s):
            %s: %s
            %s: %s
            %s: %s
            %s: %s
            %s: %s
            %s: %s
            %s: %s""",
            self._name,
            self._host,
            self._port,
            NAME_DESCRIPTION,
            self._description,
            NAME_VERSION,
            self._version,
            NAME_PROTOCOL_VERSION,
            self._protocol_version,
            NAME_LATENCY_TIME,
            self._latency,
            NAME_PLAYERS_ONLINE,
            self._players_online,
            NAME_PLAYERS_MAX,
            self._players_max,
            NAME_PLAYERS_LIST,
            self._players_list,
        )


class MinecraftServerEntity(Entity):
    """Representation of a Minecraft Server base entity."""

    def __init__(self, hass, server, name, unit, icon):
        """Initialize base entity."""
        self._server = server
        self._hass = hass
        self._state = None
        self._name = server.name() + " " + name
        self._sensor_name = name
        self._unit = unit
        self._icon = icon

        # Subscribe to signal from server instance.
        signal_name_suffix = self._server.name()
        signal_name_suffix = signal_name_suffix.replace(" ", "_")
        signal_name_suffix = signal_name_suffix.lower()
        self._signal_name = SIGNAL_NAME_PREFIX + signal_name_suffix
        async_dispatcher_connect(
            self._hass, self._signal_name, self._async_trigger_update
        )

    async def _async_trigger_update(self):
        """Triggers update of properties after receiving signal from server instance."""
        _LOGGER.debug("%s: Received signal '%s'.", self._sensor_name, self._signal_name)
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return sensor name."""
        return self._name

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
