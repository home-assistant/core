"""Support for AquaLogic devices."""

from __future__ import annotations

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
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType

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


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
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

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize the data object."""
        super().__init__(daemon=True)
        self._hass = hass
        self._host = host
        self._port = port
        self._shutdown = False
        self._panel = None

    def start_listen(self, event: Event) -> None:
        """Start event-processing thread."""
        _LOGGER.debug("Event processing thread started")
        self.start()

    def shutdown(self, event: Event) -> None:
        """Signal shutdown of processing event."""
        _LOGGER.debug("Event processing signaled exit")
        self._shutdown = True

    def data_changed(self, panel: AquaLogic) -> None:
        """Aqualogic data changed callback."""
        dispatcher_send(self._hass, UPDATE_TOPIC)

    def run(self) -> None:
        """Event thread."""

        while True:
            panel = AquaLogic()
            self._panel = panel
            panel.connect(self._host, self._port)
            panel.process(self.data_changed)

            if self._shutdown:
                return

            _LOGGER.error("Connection to %s:%d lost", self._host, self._port)
            time.sleep(RECONNECT_INTERVAL.total_seconds())

    @property
    def panel(self) -> AquaLogic | None:
        """Retrieve the AquaLogic object."""
        return self._panel
