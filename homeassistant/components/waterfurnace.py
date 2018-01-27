"""
Support for Waterfurnace component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/waterfurnace/
"""
from datetime import timedelta
import logging
import time
import threading

import voluptuous as vol

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ["waterfurnace==0.3.0"]

_LOGGER = logging.getLogger(__name__)

DOMAIN = "waterfurnace"
UPDATE_TOPIC = DOMAIN + "_update"
CONF_UNIT = "unit"
SCAN_INTERVAL = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_UNIT): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, base_config):
    """Setup waterfurnace platform."""
    import waterfurnace.waterfurnace as wf
    config = base_config.get(DOMAIN)

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    unit = config.get(CONF_UNIT)

    wfconn = wf.WaterFurnace(username, password, unit)
    # NOTE(sdague): login will throw an exception if this doesn't
    # work, which will abort the setup.
    try:
        wfconn.login()
    except wf.WFCredentialError:
        _LOGGER.error("Invalid credentials for waterfurnace login.")
        return False

    hass.data[DOMAIN] = WaterFurnaceData(hass, wfconn)
    hass.data[DOMAIN].start()

    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    return True


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
        self.unit = client.unit
        self.data = None
        self._shutdown = False

    def run(self):
        """Thread run loop."""
        @callback
        def register():
            """Connect to hass for shutdown."""
            def shutdown(event):
                """Shutdown the thread."""
                _LOGGER.debug("Signaled to shutdown.")
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

            except ConnectionError:
                # attempt to log back in if there was a session expiration.
                try:
                    self.client.login()
                except Exception:  # pylint: disable=broad-except
                    # nested exception handling, something really bad
                    # happened during the login, which means we're not
                    # in a recoverable state. Stop the thread so we
                    # don't do just keep poking at the service.
                    _LOGGER.error(
                        "Failed to refresh login credentials. Thread stopped.")
                    return
                else:
                    _LOGGER.error(
                        "Lost our connection to websocket, trying again")
                    time.sleep(SCAN_INTERVAL.seconds)

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error updating waterfurnace data.")
                time.sleep(SCAN_INTERVAL.seconds)

            else:
                self.hass.helpers.dispatcher.dispatcher_send(UPDATE_TOPIC)
                time.sleep(SCAN_INTERVAL.seconds)
