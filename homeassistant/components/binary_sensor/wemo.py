"""
Support for WeMo sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.wemo/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = ['wemo']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Register discovered WeMo binary sensors."""
    import pywemo.discovery as discovery

    if discovery_info is not None:
        location = discovery_info['ssdp_description']
        mac = discovery_info['mac_address']
        device = discovery.device_from_description(location, mac)

        if device:
            add_devices_callback([WemoBinarySensor(hass, device)])


class WemoBinarySensor(BinarySensorDevice):
    """Representation a WeMo binary sensor."""

    def __init__(self, hass, device):
        """Initialize the WeMo sensor."""
        self.wemo = device
        self._state = None

        wemo = hass.components.wemo
        wemo.SUBSCRIPTION_REGISTRY.register(self.wemo)
        wemo.SUBSCRIPTION_REGISTRY.on(self.wemo, None, self._update_callback)

    def _update_callback(self, _device, _type, _params):
        """Handle state changes."""
        _LOGGER.info("Subscription update for %s", _device)
        updated = self.wemo.subscription_update(_type, _params)
        self._update(force_update=(not updated))

        if not hasattr(self, 'hass'):
            return
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        return False

    @property
    def unique_id(self):
        """Return the id of this WeMo device."""
        return self.wemo.serialnumber

    @property
    def name(self):
        """Return the name of the service if any."""
        return self.wemo.name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    def update(self):
        """Update WeMo state."""
        self._update(force_update=True)

    def _update(self, force_update=True):
        try:
            self._state = self.wemo.get_state(force_update)
        except AttributeError as err:
            _LOGGER.warning(
                "Could not update status for %s (%s)", self.name, err)
