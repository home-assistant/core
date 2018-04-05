"""Class to hold all sensor accessories."""
import logging

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (
    CATEGORY_SENSOR, SERV_HUMIDITY_SENSOR, SERV_TEMPERATURE_SENSOR,
    CHAR_CURRENT_HUMIDITY, CHAR_CURRENT_TEMPERATURE, PROP_CELSIUS)
from .util import convert_to_float, temperature_to_homekit


_LOGGER = logging.getLogger(__name__)


@TYPES.register('TemperatureSensor')
class TemperatureSensor(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, hass, entity_id, name, **kwargs):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(name, entity_id, CATEGORY_SENSOR, **kwargs)

        self.hass = hass
        self.entity_id = entity_id

        serv_temp = add_preload_service(self, SERV_TEMPERATURE_SENSOR)
        self.char_temp = serv_temp.get_characteristic(CHAR_CURRENT_TEMPERATURE)
        self.char_temp.override_properties(properties=PROP_CELSIUS)
        self.char_temp.value = 0
        self.unit = None

    def update_state(self, entity_id=None, old_state=None, new_state=None):
        """Update temperature after state changed."""
        if new_state is None:
            return

        unit = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS)
        temperature = convert_to_float(new_state.state)
        if temperature:
            temperature = temperature_to_homekit(temperature, unit)
            self.char_temp.set_value(temperature, should_callback=False)
            _LOGGER.debug('%s: Current temperature set to %d°C',
                          self.entity_id, temperature)


@TYPES.register('HumiditySensor')
class HumiditySensor(HomeAccessory):
    """Generate a HumiditySensor accessory as humidity sensor."""

    def __init__(self, hass, entity_id, name, *args, **kwargs):
        """Initialize a HumiditySensor accessory object."""
        super().__init__(name, entity_id, CATEGORY_SENSOR, *args, **kwargs)

        self.hass = hass
        self.entity_id = entity_id

        serv_humidity = add_preload_service(self, SERV_HUMIDITY_SENSOR)
        self.char_humidity = serv_humidity \
            .get_characteristic(CHAR_CURRENT_HUMIDITY)
        self.char_humidity.value = 0

    def update_state(self, entity_id=None, old_state=None, new_state=None):
        """Update accessory after state change."""
        if new_state is None:
            return

        humidity = convert_to_float(new_state.state)
        if humidity:
            self.char_humidity.set_value(humidity, should_callback=False)
            _LOGGER.debug('%s: Percent set to %d%%',
                          self.entity_id, humidity)


@TYPES.register('BinarySensor')
class BinarySensor(HomeAccessory):
    """Generate a BinarySensor accessory as binary sensor."""

    def __init__(self, hass, state, **kwargs):
        """Initialize a BinarySensor accessory object."""
        entity_id = state.entity_id
        super().__init__(state.name, entity_id, CATEGORY_SENSOR, **kwargs)

        self.hass = hass
        self.entity_id = entity_id

        service_map = {
            'gas': ('CarbonMonoxideSensor', 'CarbonMonoxideDetected'),
            'co2': ('CarbonDioxideSensor', 'CarbonDioxideDetected'),
            'occupancy': ('OccupancySensor', 'OccupancyDetected'),
            'opening': ('ContactSensor', 'ContactSensorState'),
            'motion': ('MotionSensor', 'MotionDetected'),
            'moisture': ('LeakSensor', 'LeakDetected'),
            'smoke': ('SmokeSensor', 'SmokeDetected')}

        device_class_key = 'homekit_device_class' \
            if ('homekit_device_class' in state.attributes) \
            else 'device_class'
        device_class = state.attributes.get(device_class_key)
        service_char = service_map[device_class] \
            if (device_class in service_map) \
            else service_map['occupancy']

        service = add_preload_service(self, service_char[0])
        self.char_detected = service.get_characteristic(service_char[1])
        self.char_detected.value = 0

    def update_state(self, entity_id=None, old_state=None, new_state=None):
        """Update accessory after state change."""
        if new_state is None:
            return

        detected = (new_state.state == 'on') or (new_state.state == 'home')
        self.char_detected.set_value(detected, should_callback=False)
        _LOGGER.debug('%s: Set to %d', self.entity_id, detected)
