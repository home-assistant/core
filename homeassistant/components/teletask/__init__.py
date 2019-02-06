"""Connects to Teletask platform."""

import logging

import voluptuous as vol

from homeassistant.const import (CONF_HOST, CONF_PORT,
                                 EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyteletask==0.0.1']

DOMAIN = "teletask"

ATTR_DISCOVER_DEVICES = 'devices'

_LOGGER = logging.getLogger(__name__)

CONF_TELETASK_CONFIG = ''
CONF_TELETASK_FIRE_EVENT = "fire_event"
DATA_TELETASK = 'data_teletask'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Inclusive(CONF_TELETASK_FIRE_EVENT, 'fire_ev'):
            cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the TELETASK component."""
    from pydocstylepy.testteletask.exceptions import TeletaskException
    try:
        hass.data[DATA_TELETASK] = TeletaskModule(hass, config)
        await hass.data[DATA_TELETASK].start()

    except TeletaskException as ex:
        _LOGGER.warning("Can't connect to TELETASK interface: %s", ex)
        hass.components.persistent_notification.async_create(
            "Can't connect to TELETASK interface: <br>"
            "<b>{0}</b>".format(ex),
            title="TELETASK")

    return True


def _get_devices(hass, discovery_type):
    """Get the TELETASK devices."""
    return list(
        map(lambda device: device.name,
            filter(
                lambda device: type(device).__name__ == discovery_type,
                hass.data[DATA_TELETASK].teletask.devices)))


class TeletaskModule:
    """Representation of TELETASK Object."""

    def __init__(self, hass, config):
        """Initialize of TELETASK module."""
        self.hass = hass
        self.config = config
        self.connected = False
        self.init_teletask()
        self.register_callbacks()
        self.exposures = []

    def init_teletask(self):
        """Initialize of TELETASK object."""
        from teletask import Teletask
        self.teletask = Teletask(config=None, loop=self.hass.loop)

    async def start(self):
        """Start TELETASK object. Connect to device."""
        await self.teletask.start(host=self.config[DOMAIN][CONF_HOST],
                                  port=self.config[DOMAIN][CONF_PORT])
        await self.teletask.register_feedback()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop)
        self.connected = True

    async def stop(self, event):
        """Stop TELETASK object. Disconnect from device."""
        await self.teletask.stop()

    def register_callbacks(self):
        """Register callbacks within teletask object."""
        self.teletask.telegram_queue.register_telegram_received_cb(
            self.telegram_received_cb)

    async def telegram_received_cb(self, telegram):
        """Call invoked after a TELETASK telegram was received."""
        return False
