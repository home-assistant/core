"""Battery state for iCloud devices."""
import logging
from pprint import pprint

from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.helpers.icon import icon_for_battery_level

from . import DATA_ICLOUD, IcloudDeviceEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sensors setup."""
    if discovery_info is None:
        return

    devices = []
    for accountname, icloud_account in hass.data[DATA_ICLOUD].items():
        for devicename, device_entity in icloud_account.devices.items():
            if hasattr(device_entity, '_battery_level'):
                _LOGGER.info("Adding sensors from iCloud device=%s",
                             devicename)
                devices.append(IcloudDeviceBatterySensor(icloud_account,
                                                         device_entity._device))

    add_devices(devices, True)


class IcloudDeviceBatterySensor(IcloudDeviceEntity):
    """iCloud device Battery Sensor."""

    # def __init__(self, account, device):
    #     self._device = device
    #     _LOGGER.info('-----------------IcloudDeviceBatterySensor')
    #     pprint(vars(device))

    @property
    def unique_id(self):
        """Return a unique ID."""
        _LOGGER.info("unique_id : %s", self._dev_id + "_battery_state")
        # sensor.name displayed in dev-state, how to use unique_id ?
        return self._dev_id + "_battery_state"

    @property
    def name(self):
        """Sensor Name."""
        return self._name + " battery state"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def state(self):
        """Battery state percentage."""
        return self._battery_level

    @property
    def unit_of_measurement(self):
        """Battery state measured in percentage."""
        return '%'

    @property
    def icon(self):
        """Battery state icon handling."""
        return icon_for_battery_level(
            battery_level=self._battery_level,
            charging=self._battery_status == 'Charging'
        )
