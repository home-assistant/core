"""Support for Waterfurnaces."""

from datetime import timedelta
import logging
import threading
import time

import voluptuous as vol
from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError, WFException

from homeassistant.components import persistent_notification
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "waterfurnace"
UPDATE_TOPIC = f"{DOMAIN}_update"
SCAN_INTERVAL = timedelta(seconds=10)
ERROR_INTERVAL = timedelta(seconds=300)
MAX_FAILS = 10
NOTIFICATION_ID = "waterfurnace_website_notification"
NOTIFICATION_TITLE = "WaterFurnace website status"

CONF_UNIT = "unit"

# Support both single config and list of configs
WATERFURNACE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_UNIT): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            WATERFURNACE_SCHEMA,
            vol.All(cv.ensure_list, [WATERFURNACE_SCHEMA]),
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Set up waterfurnace platform."""

    config = base_config[DOMAIN]
    
    # Convert single config to list for uniform processing
    configs = config if isinstance(config, list) else [config]
    
    hass.data[DOMAIN] = {}
    
    for idx, entry_config in enumerate(configs):
        username = entry_config[CONF_USERNAME]
        password = entry_config[CONF_PASSWORD]
        unit = entry_config.get(CONF_UNIT)

        wfconn = WaterFurnace(username, password)
        
        # NOTE(sdague): login will throw an exception if this doesn't
        # work, which will abort the setup.
        try:
            wfconn.login()
        except WFCredentialError:
            _LOGGER.error("Invalid credentials for waterfurnace login (%s)", username)
            continue

        # If unit specified, verify it exists and use it
        # If not specified and multiple units exist, log error
        if unit:
            if unit != wfconn.gwid:
                _LOGGER.error(
                    "Specified unit %s does not match connected unit %s for %s",
                    unit,
                    wfconn.gwid,
                    username,
                )
                continue
        else:
            # If no unit specified, use the connected one
            # In the future, could detect multiple units and require specification
            unit = wfconn.gwid
        
        # Create unique key for this unit
        data_key = f"{DOMAIN}_{unit}"
        
        if data_key in hass.data[DOMAIN]:
            _LOGGER.error(
                "Unit %s already configured, skipping duplicate entry", unit
            )
            continue
            
        hass.data[DOMAIN][data_key] = WaterFurnaceData(hass, wfconn)
        hass.data[DOMAIN][data_key].start()

        discovery.load_platform(
            hass, Platform.SENSOR, DOMAIN, {"unit": unit}, entry_config
        )
    
    # Return True if at least one unit was set up successfully
    return len(hass.data[DOMAIN]) > 0


class WaterFurnaceData(threading.Thread):
    """WaterFurnace Data collector.

    This is implemented as a dedicated thread polling a websocket in a
    tight loop. The websocket will shut itself from the server side if
    a packet is not sent at least every 30 seconds. The reading is
    cheap, the login is less cheap, so keeping this open and polling
    on a very regular cadence is actually the least io intensive thing
    to do.
    """

    def __init__(self, hass, client):
        """Initialize the data object."""
        super().__init__()
        self.hass = hass
        self.client = client
        self.unit = self.client.gwid
        self.data = None
        self._shutdown = False
        self._fails = 0

    def _reconnect(self):
        """Reconnect on a failure."""

        self._fails += 1
        if self._fails > MAX_FAILS:
            _LOGGER.error("Failed to refresh login credentials. Thread stopped")
            persistent_notification.create(
                self.hass,
                (
                    "Error:<br/>Connection to waterfurnace website failed "
                    "the maximum number of times. Thread has stopped"
                ),
                title=NOTIFICATION_TITLE,
                notification_id=f"{NOTIFICATION_ID}_{self.unit}",
            )

            self._shutdown = True
            return

        # sleep first before the reconnect attempt
        _LOGGER.debug("Sleeping for fail # %s", self._fails)
        time.sleep(self._fails * ERROR_INTERVAL.total_seconds())

        try:
            self.client.login()
            self.data = self.client.read()
        except WFException:
            _LOGGER.exception("Failed to reconnect attempt %s", self._fails)
        else:
            _LOGGER.debug("Reconnected to furnace")
            self._fails = 0

    def run(self):
        """Thread run loop."""

        @callback
        def register():
            """Connect to hass for shutdown."""

            def shutdown(event):
                """Shutdown the thread."""
                _LOGGER.debug("Signaled to shutdown")
                self._shutdown = True
                self.join()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown)

        self.hass.add_job(register)

        # This does a tight loop in sending read calls to the
        # websocket. That's a blocking call, which returns pretty
        # quickly (1 second). It's important that we do this
        # frequently though, because if we don't call the websocket at
        # least every 30 seconds the server side closes the
        # connection.
        while True:
            if self._shutdown:
                _LOGGER.debug("Graceful shutdown")
                return

            try:
                self.data = self.client.read()

            except WFException:
                # WFExceptions are things the WF library understands
                # that pretty much can all be solved by logging in and
                # back out again.
                _LOGGER.exception("Failed to read data, attempting to recover")
                self._reconnect()

            else:
                dispatcher_send(self.hass, f"{UPDATE_TOPIC}_{self.unit}")
                time.sleep(SCAN_INTERVAL.total_seconds())
