"""Battery state for iCloud devices."""
import logging
from pprint import pprint

from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

from . import DATA_ICLOUD

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Sensors setup."""
    if discovery_info is None:
        return

    devices = []
    for accountname, icloud_account in hass.data[DATA_ICLOUD].items():
        for devicename, icloud_device in icloud_account.devices.items():
            if hasattr(icloud_device, '_battery_level'):
                _LOGGER.info("Adding sensors from iCloud device=%s",
                             devicename)
                devices.append(IcloudDeviceBatterySensor(hass, accountname, devicename))

    add_entities(devices, True)


class IcloudDeviceBatterySensor(Entity):
    """iCloud device Battery Sensor."""

    def __init__(self, hass, accountname, devicename):
        _LOGGER.info('-----------------IcloudDeviceBatterySensor:init')
        self._hass = hass
        self._accountname = accountname
        self._devicename = devicename

        device = self._hass.data[DATA_ICLOUD][self._accountname].devices[self._devicename]
        self._dev_id = device.dev_id + "_battery_state"
        self._name = device.name
        self._battery_level = device.battery_level
        self._battery_status = device.battery_status
        self._attrs = device.attributes


    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.info('-----------------IcloudDeviceBatterySensor:update')
        device = self._hass.data[DATA_ICLOUD][self._accountname].devices[self._devicename]
        self._battery_level = device.battery_level
        self._battery_status = device.battery_status
        self._attrs = device.attributes

    @property
    def unique_id(self):
        """Return a unique ID."""
        # sensor.name displayed in dev-state, how to use unique_id ?
        return self._dev_id

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

    @property
    def device_state_attributes(self):
        """Return default attributes for the iCloud device entity."""
        return self._attrs

