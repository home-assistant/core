"""Battery state for iCloud devices."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, DEVICE_CLASS_BATTERY
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import slugify

from .const import CONF_ACCOUNTNAME, DATA_ICLOUD

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
        hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up iCloud devices sensors based on a config entry."""

    username = entry.data[CONF_USERNAME]
    account_name = entry.data.get(
        CONF_ACCOUNTNAME,
        slugify(username.partition('@')[0])
    )
    icloud = hass.data[DATA_ICLOUD][account_name]

    # try:
    #     version = await adguard.version()
    # except AdGuardHomeConnectionError as exception:
    #     raise PlatformNotReady from exception

    devices = []
    for devicename, icloud_device in icloud.devices.items():
        if icloud_device.battery_level is not None:
            _LOGGER.debug("Adding sensors from iCloud device=%s", devicename)
            devices.append(
                IcloudDeviceBatterySensor(hass,
                                          icloud.name,
                                          devicename)
            )

    async_add_entities(devices, True)

class IcloudDeviceBatterySensor(Entity):
    """iCloud device Battery Sensor."""

    def __init__(self, hass, accountname, devicename):
        """Initialize the iCloud device battery sensor."""
        self._hass = hass
        self._accountname = accountname
        self._devicename = devicename

        device = self._hass.data[DATA_ICLOUD][
            self._accountname].devices[self._devicename]
        self._dev_id = device.dev_id + "_battery_state"
        self._name = device.name
        self._battery_level = device.battery_level
        self._battery_status = device.battery_status
        self._attrs = device.attributes

    def update(self):
        """Fetch new state data for the sensor."""
        device = self._hass.data[DATA_ICLOUD][
            self._accountname].devices[self._devicename]
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
