"""Device tracker for BMW Connected Drive vehicles.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bmw_connected_drive/
"""
import logging

from homeassistant.components.bmw_connected_drive import DOMAIN \
    as BMW_DOMAIN
from homeassistant.util import slugify

DEPENDENCIES = ['bmw_connected_drive']

_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the BMW tracker."""
    accounts = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([a.name for a in accounts]))
    for account in accounts:
        for vehicle in account.account.vehicles:
            tracker = BMWDeviceTracker(see, vehicle)
            account.add_update_listener(tracker.update)
            tracker.update()
    return True


class BMWDeviceTracker(object):
    """BMW Connected Drive device tracker."""

    def __init__(self, see, vehicle):
        """Initialize the Tracker."""
        self._see = see
        self.vehicle = vehicle

    def update(self) -> None:
        """Update the device info."""
        dev_id = slugify(self.vehicle.modelName)
        _LOGGER.debug('Updating %s', dev_id)
        attrs = {
            'trackr_id': dev_id,
            'id': dev_id,
            'name': self.vehicle.modelName
        }
        self._see(
            dev_id=dev_id, host_name=self.vehicle.modelName,
            gps=self.vehicle.state.gps_position, attributes=attrs,
            icon='mdi:car'
        )
