"""Support for Home Assistant Android app sensors."""
from homeassistant.components import android
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

DEPENDENCIES = ['android']

SENSOR_TYPES = {
    'level': ['Battery Level', '%'],
    'state': ['Battery State', None]
}

DEFAULT_ICON_LEVEL = 'mdi:battery'
DEFAULT_ICON_STATE = 'mdi:power-plug'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Android sensor."""
    # Leave here for if someone accidentally adds platform: android to config


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Android from a config entry."""
    dev = list()
    for device_name, device in android.devices(hass).items():
        for sensor_type in ('level', 'state'):
            dev.append(AndroidSensor(sensor_type, device_name, device))

    async_add_entities(dev, True)


class AndroidSensor(Entity):
    """Representation of an Android sensor."""

    def __init__(self, sensor_type, device_name, device):
        """Initialize the sensor."""
        self._device_name = device_name
        self._name = "{} {}".format(device_name, SENSOR_TYPES[sensor_type][0])
        self._device = device
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            'identifiers': {
                (android.DOMAIN,
                 self._device[android.ATTR_DEVICE][android.ATTR_DEVICE_PERMANENT_ID]),
            },
            'name': self._device[android.ATTR_DEVICE][android.ATTR_DEVICE_NAME],
            'manufacturer': 'Apple',
            'model': self._device[android.ATTR_DEVICE][android.ATTR_DEVICE_TYPE],
            'sw_version':
            self._device[android.ATTR_DEVICE][android.ATTR_DEVICE_SYSTEM_VERSION],
        }

    @property
    def name(self):
        """Return the name of the Android sensor."""
        device_name = self._device[android.ATTR_DEVICE][android.ATTR_DEVICE_NAME]
        return "{} {}".format(device_name, SENSOR_TYPES[self.type][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        device_id = self._device[android.ATTR_DEVICE_ID]
        return "{}_{}".format(self.type, device_id)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        device = self._device[android.ATTR_DEVICE]
        device_battery = self._device[android.ATTR_BATTERY]
        return {
            "Battery State": device_battery[android.ATTR_BATTERY_STATE],
            "Battery Level": device_battery[android.ATTR_BATTERY_LEVEL],
            "Device Type": device[android.ATTR_DEVICE_TYPE],
            "Device Name": device[android.ATTR_DEVICE_NAME],
            "Device Version": device[android.ATTR_DEVICE_SYSTEM_VERSION],
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        device_battery = self._device[android.ATTR_BATTERY]
        battery_state = device_battery[android.ATTR_BATTERY_STATE]
        battery_level = device_battery[android.ATTR_BATTERY_LEVEL]
        charging = True
        icon_state = DEFAULT_ICON_STATE
        if battery_state in (android.ATTR_BATTERY_STATE_FULL,
                             android.ATTR_BATTERY_STATE_UNPLUGGED):
            charging = False
            icon_state = "{}-off".format(DEFAULT_ICON_STATE)
        elif battery_state == android.ATTR_BATTERY_STATE_UNKNOWN:
            battery_level = None
            charging = False
            icon_state = "{}-unknown".format(DEFAULT_ICON_LEVEL)

        if self.type == "state":
            return icon_state
        return icon_for_battery_level(battery_level=battery_level,
                                      charging=charging)

    def update(self):
        """Get the latest state of the sensor."""
        self._device = android.devices(self.hass).get(self._device_name)
        self._state = self._device[android.ATTR_BATTERY][self.type]
