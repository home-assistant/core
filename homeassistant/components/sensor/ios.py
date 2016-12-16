"""
Support for Home Assistant iOS app sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/ecosystem/ios/
"""
from homeassistant.components import ios
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ["ios"]

SENSOR_TYPES = {
    "level": ["Battery Level", "%"],
    "state": ["Battery State", None]
}

DEFAULT_ICON = "mdi:battery"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the iOS sensor."""
    if discovery_info is None:
        return
    dev = list()
    for device_name, device in ios.devices().items():
        for sensor_type in ("level", "state"):
            dev.append(IOSSensor(sensor_type, device_name, device))

    add_devices(dev)


class IOSSensor(Entity):
    """Representation of an iOS sensor."""

    def __init__(self, sensor_type, device_name, device):
        """Initialize the sensor."""
        self._device_name = device_name
        self._name = device_name + " " + SENSOR_TYPES[sensor_type][0]
        self._device = device
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.update()

    @property
    def name(self):
        """Return the name of the iOS sensor."""
        device_name = self._device[ios.ATTR_DEVICE][ios.ATTR_DEVICE_NAME]
        return "{} {}".format(device_name, SENSOR_TYPES[self.type][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return "sensor_ios_battery_{}_{}".format(self.type, self._device_name)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        device = self._device[ios.ATTR_DEVICE]
        device_battery = self._device[ios.ATTR_BATTERY]
        return {
            "Battery State": device_battery[ios.ATTR_BATTERY_STATE],
            "Battery Level": device_battery[ios.ATTR_BATTERY_LEVEL],
            "Device Type": device[ios.ATTR_DEVICE_TYPE],
            "Device Name": device[ios.ATTR_DEVICE_NAME],
            "Device Version": device[ios.ATTR_DEVICE_SYSTEM_VERSION],
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        device_battery = self._device[ios.ATTR_BATTERY]
        battery_state = device_battery[ios.ATTR_BATTERY_STATE]
        battery_level = device_battery[ios.ATTR_BATTERY_LEVEL]
        rounded_level = round(battery_level, -1)
        returning_icon = DEFAULT_ICON
        if battery_state == ios.ATTR_BATTERY_STATE_FULL:
            returning_icon = DEFAULT_ICON
        elif battery_state == ios.ATTR_BATTERY_STATE_CHARGING:
            # Why is MDI missing 10, 50, 70?
            if rounded_level in (20, 30, 40, 60, 80, 90, 100):
                returning_icon = "{}-charging-{}".format(DEFAULT_ICON,
                                                         str(rounded_level))
            else:
                returning_icon = "{}-charging".format(DEFAULT_ICON)
        elif battery_state == ios.ATTR_BATTERY_STATE_UNPLUGGED:
            if rounded_level < 10:
                returning_icon = "{}-outline".format(DEFAULT_ICON)
            elif battery_level == 100:
                returning_icon = DEFAULT_ICON
            else:
                returning_icon = "{}-{}".format(DEFAULT_ICON,
                                                str(rounded_level))
        elif battery_state == ios.ATTR_BATTERY_STATE_UNKNOWN:
            returning_icon = "{}-unknown".format(DEFAULT_ICON)

        return returning_icon

    def update(self):
        """Get the latest state of the sensor."""
        self._device = ios.devices().get(self._device_name)
        self._state = self._device[ios.ATTR_BATTERY][self.type]
