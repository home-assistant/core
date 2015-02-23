import homeassistant.components.zwave as zwave
from homeassistant.helpers import Device
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_BATTERY_LEVEL, ATTR_UNIT_OF_MEASUREMENT,
    TEMP_CELCIUS, TEMP_FAHRENHEIT, LIGHT_LUX, ATTR_LOCATION)


def devices_discovered(hass, config, info):
    """ """
    from louie import connect
    from openzwave.network import ZWaveNetwork

    VALUE_CLASS_MAP = {
        zwave.VALUE_TEMPERATURE: ZWaveTemperatureSensor,
        zwave.VALUE_LUMINANCE: ZWaveLuminanceSensor,
        zwave.VALUE_RELATIVE_HUMIDITY: ZWaveRelativeHumiditySensor,
    }

    sensors = []

    for node in zwave.NETWORK.nodes.values():
        for value, klass in VALUE_CLASS_MAP.items():
            if value in node.values:
                sensors.append(klass(node))

                if sensors[-1] is None:
                    print("")
                    print("WTF BBQ")
                    print(node, klass)
                    print("")
                    continue

    def value_changed(network, node, value):
        """ """
        print("")
        print("")
        print("")
        print("ValueChanged in sensor !!", node, value)
        print("")
        print("")
        print("")

    # triggered when sensors have updated
    connect(value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED, weak=False)

    return sensors


class ZWaveSensor(Device):
    def __init__(self, node, sensor_value):
        self._node = node
        self._value = node.values[sensor_value]

    @property
    def unique_id(self):
        """ Returns a unique id. """
        return "ZWAVE-{}-{}".format(self._node.node_id, self._value)

    @property
    def name(self):
        """ Returns the name of the device. """
        name = self._node.name or "{} {}".format(
            self._node.manufacturer_name, self._node.product_name)

        return "{} {}".format(name, self._value.label)

    @property
    def state(self):
        """ Returns the state of the sensor. """
        return self._value.data

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        attrs = {
            ATTR_FRIENDLY_NAME: self.name
        }

        battery_level = zwave.get_node_value(
            self._node, zwave.VALUE_BATTERY_LEVEL)

        if battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = battery_level

        unit = self.unit

        if unit is not None:
            attrs[ATTR_UNIT_OF_MEASUREMENT] = unit

        location = self._node.location

        if location:
            attrs[ATTR_LOCATION] = location

        attrs.update(self.get_sensor_attributes())

        return attrs

    @property
    def unit(self):
        """ Unit if sensor has one. """
        return None

    def get_sensor_attributes(self):
        """ Get sensor attributes. """
        return {}


class ZWaveTemperatureSensor(ZWaveSensor):
    """ Represents a ZWave Temperature Sensor. """

    def __init__(self, node):
        super().__init__(node, zwave.VALUE_TEMPERATURE)

    @property
    def state(self):
        """ Returns the state of the sensor. """
        return round(self._value.data/1000, 1)

    @property
    def unit(self):
        """ Unit of this sensor. """
        unit = self._value.units

        if unit == 'C':
            return TEMP_CELCIUS
        elif unit == 'F':
            return TEMP_FAHRENHEIT
        else:
            return None


class ZWaveRelativeHumiditySensor(ZWaveSensor):
    """ Represents a ZWave Relative Humidity Sensor. """

    def __init__(self, node):
        super().__init__(node, zwave.VALUE_RELATIVE_HUMIDITY)

    @property
    def unit(self):
        """ Unit of this sensor. """
        return '%'


class ZWaveLuminanceSensor(ZWaveSensor):
    """ Represents a ZWave luminance Sensor. """

    def __init__(self, node):
        super().__init__(node, zwave.VALUE_LUMINANCE)

    @property
    def unit(self):
        """ Unit of this sensor. """
        return LIGHT_LUX
