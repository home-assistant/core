"""
Support for WeMo sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.wemo/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.loader import get_component

DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument, too-many-function-args
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Register discovered WeMo binary sensors."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info[2]
        mac = discovery_info[3]
        device = discovery.device_from_description(location, mac)

        if device:
            add_devices_callback([WemoBinarySensor(device)])


class WemoBinarySensor(BinarySensorDevice):
    """Represents a WeMo binary sensor."""

    def __init__(self, device):
        """Initialize the WeMo sensor."""
        self.wemo = device
        self._state = None

        wemo = get_component('wemo')
        wemo.SUBSCRIPTION_REGISTRY.register(self.wemo)
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _params):
        """Called by the wemo device callback to update state."""
        _LOGGER.info(
            'Subscription update for  %s',
            _device)
        if not hasattr(self, 'hass'):
            self.update()
            return
        self.update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        return False

    @property
    def unique_id(self):
        """Return the id of this WeMo device."""
        return "{}.{}".format(self.__class__, self.wemo.serialnumber)

    @property
    def name(self):
        """Return the name of the sevice if any."""
        return self.wemo.name

    @property
    def is_on(self):
        """True if sensor is on."""
        return self._state

    def update(self):
        """Update WeMo state."""
        try:
            self._state = self.wemo.get_state(True)
        except AttributeError:
            _LOGGER.warning('Could not update status for %s', self.name)
