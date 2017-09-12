"""
Component for Lutron QSE network interface (QSE-CI-NWK-E).

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lutron_qse/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pylutron-qse==0.1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'lutron_qse'
LUTRON_QSE_INSTANCE = DOMAIN + '_instance'
LUTRON_QSE_IGNORE = DOMAIN + '_ignore'
LUTRON_QSE_COMPONENTS = [
    'cover'
]
CONF_IGNORE = 'ignore'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_IGNORE, default=[]):
            vol.All(cv.ensure_list, [cv.string]),
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, base_config):
    """Setup Lutron QSE component."""
    # pylint: disable=import-error
    from pylutron_qse.qse import QSE

    config = base_config.get(DOMAIN)
    hass.data[LUTRON_QSE_INSTANCE] = QSE(config[CONF_HOST])
    hass.data[LUTRON_QSE_IGNORE] = config[CONF_IGNORE]
    if not hass.data[LUTRON_QSE_INSTANCE].connected():
        _LOGGER.error("Unable to connect to Lutron QSE at %s",
                      config[CONF_HOST])
        return False

    _LOGGER.info("Connected to Lutron QSE at %s", config[CONF_HOST])
    for component in LUTRON_QSE_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)
    return True


class LutronQSEDevice(Entity):
    """Common base class for all Lutron QSE devices."""

    def __init__(self, device):
        """Set up the base class.

        [:param]device the pylutron_qse.Device instance
        """
        self._device = device

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.async_add_job(
            self._device.add_subscriber, self._update_callback)

    def _update_callback(self):
        self._update()
        self.schedule_update_ha_state()

    def _update(self):
        """Subclass should override to update their state."""
        pass

    @property
    def name(self):
        """Return the name of the device."""
        if self._device.integration_id is not None:
            return self._device.integration_id
        return self._device.serial_number

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {
            'serial_number': self._device.serial_number,
        }
        return attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self._device.connected()

    @property
    def should_poll(self):
        """No polling needed."""
        return False
