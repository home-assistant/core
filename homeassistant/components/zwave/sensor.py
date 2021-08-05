"""Support for Z-Wave sensors."""
from homeassistant.components.sensor import DEVICE_CLASS_BATTERY, DOMAIN, SensorEntity
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import ZWaveDeviceEntity, const


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Sensor from Config Entry."""

    @callback
    def async_add_sensor(sensor):
        """Add Z-Wave Sensor."""
        async_add_entities([sensor])

    async_dispatcher_connect(hass, "zwave_new_sensor", async_add_sensor)


def get_device(node, values, **kwargs):
    """Create Z-Wave entity device."""
    # Generic Device mappings
    if values.primary.command_class == const.COMMAND_CLASS_BATTERY:
        return ZWaveBatterySensor(values)
    if node.has_command_class(const.COMMAND_CLASS_SENSOR_MULTILEVEL):
        return ZWaveMultilevelSensor(values)
    if (
        node.has_command_class(const.COMMAND_CLASS_METER)
        and values.primary.type == const.TYPE_DECIMAL
    ):
        return ZWaveMultilevelSensor(values)
    if node.has_command_class(const.COMMAND_CLASS_ALARM) or node.has_command_class(
        const.COMMAND_CLASS_SENSOR_ALARM
    ):
        return ZWaveAlarmSensor(values)
    return None


class ZWaveSensor(ZWaveDeviceEntity, SensorEntity):
    """Representation of a Z-Wave sensor."""

    def __init__(self, values):
        """Initialize the sensor."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self.update_properties()

    def update_properties(self):
        """Handle the data changes for node values."""
        self._state = self.values.primary.data
        self._units = self.values.primary.units

    @property
    def force_update(self):
        """Return force_update."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement the value is expressed in."""
        return self._units


class ZWaveMultilevelSensor(ZWaveSensor):
    """Representation of a multi level sensor Z-Wave sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._units in ("C", "F"):
            return round(self._state, 1)
        if isinstance(self._state, float):
            return round(self._state, 2)

        return self._state

    @property
    def device_class(self):
        """Return the class of this device."""
        if self._units in ["C", "F"]:
            return DEVICE_CLASS_TEMPERATURE
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        if self._units == "C":
            return TEMP_CELSIUS
        if self._units == "F":
            return TEMP_FAHRENHEIT
        return self._units


class ZWaveAlarmSensor(ZWaveSensor):
    """Representation of a Z-Wave sensor that sends Alarm alerts.

    Examples include certain Multisensors that have motion and vibration
    capabilities. Z-Wave defines various alarm types such as Smoke, Flood,
    Burglar, CarbonMonoxide, etc.

    This wraps these alarms and allows you to use them to trigger things, etc.

    COMMAND_CLASS_ALARM is what we get here.
    """


class ZWaveBatterySensor(ZWaveSensor):
    """Representation of Z-Wave device battery level."""

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_BATTERY
