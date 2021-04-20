"""Support for AquaLogic devices."""
from datetime import timedelta
import logging
import threading
import time

from aqualogic.core import AquaLogic
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "aqualogic"
UPDATE_TOPIC = f"{DOMAIN}_update"
CONF_UNIT = "unit"
RECONNECT_INTERVAL = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.port}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up AquaLogic platform."""
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    processor = AquaLogicProcessor(hass, host, port)
    hass.data[DOMAIN] = processor
    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, processor.start_listen)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, processor.shutdown)
    _LOGGER.debug("AquaLogicProcessor %s:%i initialized", host, port)
    return True


class AquaLogicProcessor(threading.Thread):
    """AquaLogic event processor thread."""

    def __init__(self, hass, host, port):
        """Initialize the data object."""
        super().__init__(daemon=True)
        self._hass = hass
        self._host = host
        self._port = port
        self._shutdown = False
        self._panel = None

    def start_listen(self, event):
        """Start event-processing thread."""
        _LOGGER.debug("Event processing thread started")
        self.start()

    def shutdown(self, event):
        """Signal shutdown of processing event."""
        _LOGGER.debug("Event processing signaled exit")
        self._shutdown = True

    def data_changed(self, panel):
        """Aqualogic data changed callback."""
        self._hass.helpers.dispatcher.dispatcher_send(UPDATE_TOPIC)

    def run(self):
        """Event thread."""

        while True:
            self._panel = AquaLogic()
            self._panel.connect(self._host, self._port)
            self._panel.process(self.data_changed)

            if self._shutdown:
                return

            _LOGGER.error("Connection to %s:%d lost", self._host, self._port)
            time.sleep(RECONNECT_INTERVAL.seconds)

    @property
    def panel(self):
        """Retrieve the AquaLogic object."""
        return self._panel
