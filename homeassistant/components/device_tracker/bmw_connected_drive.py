"""Device tracker for BMW Connected Drive vehicles.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bmw_connected_drive/
"""
import logging

from homeassistant.components.bmw_connected_drive import DOMAIN \
    as BMW_DOMAIN
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['bmw_connected_drive']


def setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up the BMW tracker."""
    entities = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BMW accounts: %s',
                  ', '.join([v.name for v in entities]))
    for entity in entities:
        account = entity.account
        for vehicle in account.vehicles:
            BMWDeviceTracker(async_see, entity, account, vehicle)
    return True


class BMWDeviceTracker(object):
    """BMW Connected Drive device tracker."""

    def __init__(self, async_see, entity, account, vehicle):
        """Initialize the Tracker."""
        self._async_see = async_see
        self.account = account
        self.vehicle = vehicle
        entity.add_update_listener(self.update)

    def update(self) -> None:
        """Update the device info."""
        dev_id = slugify(self.vehicle.modelName)
        attrs = {
            'trackr_id': dev_id,
            'id': dev_id,
            'name': self.vehicle.modelName
        }
        self._async_see(
            dev_id=dev_id, host_name=self.vehicle.modelName,
            gps=self.vehicle.state.gps_position, attributes=attrs,
            icon='mdi:car'
        )
