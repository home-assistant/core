"""Support for the MAX! Cube LAN Gateway."""
import logging
from socket import timeout
from threading import Lock
import time

from maxcube.cube import MaxCube
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import now

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 62910
DOMAIN = "maxcube"

DATA_KEY = "maxcube"

NOTIFICATION_ID = "maxcube_notification"
NOTIFICATION_TITLE = "Max!Cube gateway setup"

CONF_GATEWAYS = "gateways"

CONFIG_GATEWAY = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SCAN_INTERVAL, default=300): cv.time_period,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_GATEWAYS, default={}): vol.All(
                    cv.ensure_list, [CONFIG_GATEWAY]
                )
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.CLIMATE,
    Platform.BINARY_SENSOR,
]


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Establish connection to MAX! Cube."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    if DOMAIN not in config or CONF_GATEWAYS not in config[DOMAIN]:
        return True

    _LOGGER.warning(
        "Configuration of the maxcube platform in YAML is deprecated and will be "
        "removed in future release; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )

    gateways = config[DOMAIN][CONF_GATEWAYS]
    for gateway in gateways:
        data = {
            CONF_HOST: gateway[CONF_HOST],
            CONF_PORT: gateway[CONF_PORT],
            CONF_SCAN_INTERVAL: gateway[CONF_SCAN_INTERVAL].total_seconds(),
        }

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=data,
            )
        )

    return True


class MaxCubeHandle:
    """Keep the cube instance in one place and centralize the update."""

    def __init__(self, cube, scan_interval):
        """Initialize the Cube Handle."""
        self.cube = cube
        self.cube.use_persistent_connection = scan_interval <= 300  # seconds
        self.scan_interval = scan_interval
        self.mutex = Lock()
        self._updatets = time.monotonic()

    def update(self):
        """Pull the latest data from the MAX! Cube."""
        # Acquire mutex to prevent simultaneous update from multiple threads
        with self.mutex:
            # Only update every update_interval
            if (time.monotonic() - self._updatets) >= self.scan_interval:
                _LOGGER.debug("Updating")

                try:
                    self.cube.update()
                except timeout:
                    _LOGGER.error("Max!Cube connection failed")
                    return False

                self._updatets = time.monotonic()
            else:
                _LOGGER.debug("Skipping update")

    def disconnect(self):
        """Disconnect from cube."""
        with self.mutex:
            self.cube.disconnect()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    config = entry.data

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    # Get configs
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    scan_interval = config[CONF_SCAN_INTERVAL]

    entry.add_update_listener(async_reload_entry)

    if host in hass.data[DATA_KEY]:
        # Already configured, do nothing
        _LOGGER.debug("Already configured, do nothing")
        return True

    try:
        cube = MaxCube(host, port, now=now)
        hass.data[DATA_KEY][host] = MaxCubeHandle(cube, scan_interval)
    except timeout as ex:
        _LOGGER.error("Unable to connect to Max!Cube gateway: %s", str(ex))
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />You will need to reload integration after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    host = entry.data[CONF_HOST]

    if host not in hass.data[DATA_KEY]:
        # Do nothing
        return unload_ok

    handler = hass.data[DATA_KEY].pop(host)
    handler.disconnect()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
