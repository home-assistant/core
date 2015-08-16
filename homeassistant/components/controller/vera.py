"""
homeassistant.components.controller.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This controller component is responsible for communication with a VeraLite
Z-Wave controller.  It retrieves the device information from the Vera and
and using the discovery mechanism creates components for each Vera device.
Each Vera device may then create one or more child devices for interacting
with or monitoring various properties of the vera device.  This builds a
tree structure like the example below.

Controller
        |-Switch
        |    |-Child Sensor
        |
        |-Sensor
        |   |-Child Switch
        |   |-Child Sensor 1
        |   |-Child Sensor 2
        |
        |-Light
        |   |-Child Sensor

This controller provides a central point for communication with the Vera
and cuts down the amount of requests sent in the previous implementation.
The discovered child devices monitor the state change event of the controller
and are responsible for updating their states when their relevant data
changes.  The child devices use services to communicate with this controller
which in turn handles the communication with the Vera unit.

To configure the controller you will need to add something like this to
your configuration file:

controller:
  platform: vera
  vera_controller_url: http://192.168.1.111:3480/
  default_switches_to_light: true
  device_data:
    # Exclduing the child temperature sensor
    50:
        temperature:
          exclude: true

    # Excluding a device with a vera id of 32
    32:
      exclude: true

    # Hiding vera device 35 from the states UI
    35:
      hidden: true

    # Specifying that a switch is a light
    36:
      is_light: true

    # Overriding the name of the vera device 39
    39:
        name: 'Loungeroom Lights'

    # Overriding the name of the child humidity sensor
    40:
        humidity:
            name: 'Lounge Humidity'

"""
from homeassistant.components.sensor import (
    DISCOVER_CHILD_SENSORS, DISCOVER_VERA_SENSORS)
from homeassistant.components.switch import (
    DISCOVER_CHILD_SWITCHES, DISCOVER_VERA_SWITCHES)
from homeassistant.components.light import (
    DISCOVER_CHILD_LIGHTS, ATTR_BRIGHTNESS, DISCOVER_VERA_LIGHTS)
from homeassistant.components.controller import (
    DOMAIN)

from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED,
    ATTR_DISCOVERED,
    ATTR_SERVICE,
    ATTR_TRIPPED,
    TEMP_CELCIUS,
    TEMP_FAHRENHEIT,
    ATTR_BATTERY_LEVEL,
    ATTR_ARMED,
    STATE_ON,
    ATTR_HIDDEN,
    STATE_NOT_TRIPPED,
    STATE_TRIPPED,
    ATTR_LAST_TRIP_TIME)

import logging
import homeassistant.util.dt as dt_util
from homeassistant.components.controller import Controller
from homeassistant.helpers.entity import Entity
from requests.exceptions import RequestException
# pylint: disable=no-name-in-module, import-error
import homeassistant.external.vera.vera as veraApi

SERVICE_SET_VAL = 'service_set_vera_value'

STATE_AVAILABLE = 'available'
STATE_UNAVAILABLE = 'unavailable'
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Set up the Vera controller and kick off device discovery. """
    base_url = config.get('vera_controller_url', False)
    if not base_url:
        _LOGGER.error(
            "The required parameter 'vera_controller_url'"
            " was not found in config"
        )
        return False

    try:
        vera_api = veraApi.VeraController(base_url)
        devices = vera_api.refresh_data()
    except RequestException:
        # There was a network related error connecting to the vera controller
        _LOGGER.exception("Error communicating with Vera API")
        return False

    vera_controller = VeraController(hass, config, vera_api)
    vera_devices = [vera_controller]

    add_devices_callback(vera_devices)

    switch_categories = [
        'On/Off Switch',
        'Switch',
        'Dimmable Switch']
    device_data = config.get('device_data', {})
    for key, value in devices.items():
        child_config = device_data.get(key, {})
        if child_config.get('exclude', False):
            continue

        if value.get('categoryName', '') in switch_categories:
            discover_swtich(
                config, child_config, vera_controller, value, hass)
        else:
            discover_sensor(
                config, child_config, vera_controller, value, hass)

    def set_value_service(service):
        """ The service called by switches to change values on the Vera """
        device_id = service.data.get('extra_data').get('vera_device_id')
        variable = service.data.get('extra_data').get('vera_variable')

        val = 0
        if service.data.get('action') == 'dim':
            brightness = int(service.data.get(ATTR_BRIGHTNESS))
            val = round((brightness / 255) * 100)
        else:
            state = service.data.get('state')
            if state == STATE_ON:
                val = 1

        vera_controller.vera_api.set_value(device_id, variable, val)

    hass.services.register(DOMAIN, SERVICE_SET_VAL, set_value_service)


def discover_swtich(
        config, child_config, vera_controller, device_data, hass):
    """ Fire the discovery event for a switch """
    is_dimmable = (
        True if device_data.get('categoryName') == 'Dimmable Switch'
        else False)

    is_light = child_config.get(
        'is_light', config.get(
            'default_switches_to_light', is_dimmable))

    data = {}
    data['name'] = child_config.get('name', device_data.get('name'))
    data['parent_entity_id'] = vera_controller.entity_id
    data['parent_entity_domain'] = DOMAIN
    data['vera_id'] = device_data.get('id')
    if is_dimmable:
        data['light_type'] = 'dimmer'

    if is_dimmable:
        data['state_variable'] = 'level'
    else:
        data['state_variable'] = 'status'

    data['config_data'] = child_config
    data['device_data'] = device_data

    discover_type = (
        DISCOVER_VERA_LIGHTS if is_light
        else DISCOVER_VERA_SWITCHES)

    hass.bus.fire(
        EVENT_PLATFORM_DISCOVERED, {
            ATTR_SERVICE: discover_type,
            ATTR_DISCOVERED: data})


def discover_sensor(
        config, child_config, vera_controller, device_data, hass):
    """ Fire the discovery event for a sensor """
    data = {}
    data['name'] = child_config.get('name', device_data.get('name'))
    data['parent_entity_id'] = vera_controller.entity_id
    data['vera_id'] = device_data.get('id')
    child_config['temperature_units'] = child_config.get(
        'temperature_units', vera_controller.temperature_units)
    data['config_data'] = child_config
    data['device_data'] = device_data
    hass.bus.fire(
        EVENT_PLATFORM_DISCOVERED, {
            ATTR_SERVICE: DISCOVER_VERA_SENSORS,
            ATTR_DISCOVERED: data})


class VeraController(Controller):
    """ This entity represents a Vera controller device.
    It is responsible for handling the communication between the Vera and
    discovered child entities """
    def __init__(self, hass, config, vera_api):
        self._state = STATE_AVAILABLE
        self._vera_api = vera_api
        self._name = config.get('name', vera_api.model)
        self.child_devices = {}
        self._vera_device_data = {}

    @property
    def state_attributes(self):
        attr = super().state_attributes
        attr['model'] = self._vera_api.model
        attr['version'] = self._vera_api.version
        attr['serial_number'] = self._vera_api.serial_number
        attr['vera_device_data'] = self._vera_device_data

        return attr

    def update(self):
        """ Update the state of the device """
        try:
            devices = self._vera_api.refresh_data()
            for key, value in devices.items():
                if not self.child_devices.get(key, False):
                    continue
                self.child_devices.get(key).set_device_data(value)
            self._vera_device_data = devices
            self._state = STATE_AVAILABLE
        except RequestException:
            # There was a network related error connecting to the controller
            _LOGGER.exception("Error communicating with Vera API")
            self._state = STATE_UNAVAILABLE

    @property
    def vera_api(self):
        """ Get the Vera API instance. """
        return self._vera_api

    @property
    def name(self):
        """ Get the mame of the Controller. """
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def temperature_units(self):
        """ Get the temperature units of the Controller. """
        return self._vera_api.temperature_units

    @property
    def device_type(self):
        return 'VeraLite'

    @property
    def model(self):
        return self._vera_api.model

    @property
    def version(self):
        return self._vera_api.version


# pylint: disable=too-many-public-methods
class VeraControllerDevice(Entity):
    """ This is a base class that devices that are discovered by the
    Vera Controller entity.  It covers basic functionality common to
    all Vera devices """

    def __init__(self, hass, config, device_data):
        self._state = None
        self._device_data = device_data
        self._name = config.get('name', self._device_data.get('name'))
        self._config = config
        self._hass = hass
        self._state_variable = self._config.get('state_variable', 'id')
        self._parent_entity_id = config.get('parent_entity_id', None)

    @property
    def state_attributes(self):
        attr = super().state_attributes
        attr['vera_id'] = self._device_data.get('id')

        if 'lasttrip' in self._device_data.keys():
            last_trip_dt = dt_util.utc_from_timestamp(
                int(self._device_data.get('lasttrip', 0)))
            attr[ATTR_LAST_TRIP_TIME] = dt_util.datetime_to_str(last_trip_dt)

        if self.has_temperature:
            # pylint: disable=unused-variable
            temp, units = self.get_temperature()
            attr['temperature'] = temp

        if self.is_trippable:
            attr[ATTR_TRIPPED] = (
                'True' if str(self._device_data.get('tripped')) == '1'
                else 'False')

        if self.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self._device_data.get('batterylevel')

        if self.has_lightlevel:
            attr['light_level'] = self._device_data.get('light')

        if self.has_humidity:
            attr['humidity'] = self._device_data.get('humidity')

        if self.is_armable:
            attr[ATTR_ARMED] = (
                'True' if str(self._device_data.get('armed')) == '1'
                else 'False')

        if self.is_armedtripped:
            attr['armed_tripped'] = (
                'True' if str(self._device_data.get('armedtripped')) == '1'
                else 'False')

        if self.is_switchable:
            attr['status'] = (
                'True' if str(self._device_data.get('status')) == '1'
                else 'False')

        if self.is_dimmable:
            attr['status'] = (
                'True' if str(self._device_data.get('status')) == '1'
                else 'False')
            attr['level'] = self._device_data.get('level')
            attr[ATTR_BRIGHTNESS] = self.get_brightness()

        attr[ATTR_HIDDEN] = self._config.get('hidden', False)
        if self._parent_entity_id is not None:
            attr['parent_entity_id'] = self._parent_entity_id

        attr['state_variable'] = self._state_variable

        return attr

    def set_device_data(self, device_data):
        """ For convenience, simply sets the device data and
        updates the entity state. """
        self._device_data = device_data
        self.update_ha_state()

    @property
    def name(self):
        """ Get the mame of the Controller. """
        return self._name

    def get_temperature(self):
        """ Get the temperature and units. """
        current_temp = self._device_data.get('temperature')
        vera_temp_units = self._config.get('temperature_units', TEMP_CELCIUS)

        if vera_temp_units == 'F':
            temperature_units = TEMP_FAHRENHEIT
        else:
            temperature_units = TEMP_CELCIUS

        return self._hass.config.temperature(
            current_temp,
            temperature_units)

    @property
    def state(self):
        return self._state

    @property
    def should_poll(self):
        """
        Polling is not required as state is updated from the parent
        """
        return False

    @property
    def is_trippable(self):
        """ Returns true if the device supports a trippable state """
        return True if 'tripped' in self._device_data.keys() else False

    @property
    def is_armable(self):
        """ Returns true if the device supports a armable state """
        return True if 'armed' in self._device_data.keys() else False

    @property
    def is_armedtripped(self):
        """ Returns true if the device is armed and tripped """
        return True if 'armedtripped' in self._device_data.keys() else False

    @property
    def has_battery(self):
        """ Returns true if the device supports battery level """
        return True if 'batterylevel' in self._device_data.keys() else False

    @property
    def has_temperature(self):
        """ Returns true if the device supports temperature level """
        return True if 'temperature' in self._device_data.keys() else False

    @property
    def has_lightlevel(self):
        """ Returns true if the device supports light level """
        return True if 'light' in self._device_data.keys() else False

    @property
    def has_humidity(self):
        """ Returns true if the device has a humidity reading """
        return True if 'humidity' in self._device_data.keys() else False

    @property
    def is_switchable(self):
        """ Returns true if the device supports switching """
        if (self.category_name == "On/Off Switch"
                or self.category_name == "Switch"):
            return True
        else:
            return False

    @property
    def is_dimmable(self):
        """ Returns true if the device supports dimming """
        if self.category_name == "Dimmable Switch":
            return True
        else:
            return False

    @property
    def category_name(self):
        """ Returns the vera category name """
        return self._device_data.get('categoryName', 'None')

    # pylint: disable=too-many-statements
    def create_child_devices(self):
        """ Create child devices based on available properties.
        This method is rather long but it is basically responsible for
        checking the properties of the vera device and creating child
        sensors and switches to alter or monitor additional properties
        as well as the parent device's main function. """

        if (self.has_temperature
                and not self.should_exclude_child('temperature')):
            temp, units = self.get_temperature()
            data = {}
            data['name'] = (
                self._config.get('temperature', {}).get('name', self._name))
            data['parent_entity_id'] = self.entity_id
            data['watched_variable'] = 'temperature'
            data['initial_state'] = temp
            data['unit_of_measurement'] = units
            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('temperature'))
            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_CHILD_SENSORS,
                    ATTR_DISCOVERED: data})

        if self.is_trippable and not self.should_exclude_child('tripped'):
            data = {}
            data['name'] = (
                self._config.get('tripped', {}).get('name', self._name))
            data['parent_entity_id'] = self.entity_id
            data['watched_variable'] = ATTR_TRIPPED
            data['value_map'] = {
                'True': STATE_TRIPPED,
                'False': STATE_NOT_TRIPPED
            }
            data['initial_state'] = (
                'True' if str(self._device_data.get('tripped')) == '1'
                else 'False')
            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('tripped'))
            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_CHILD_SENSORS,
                    ATTR_DISCOVERED: data})

        if (self.is_armedtripped and not
                self.should_exclude_child('armed_tripped')):
            data = {}
            data['name'] = (
                self._config.get('armed_tripped', {}).get('name', self._name))
            if self.is_trippable:
                data['name'] = (
                    self._config.get('armed_tripped', {}).get(
                        'name', self._name + ' Arm Tripped'))
            data['parent_entity_id'] = self.entity_id
            data['watched_variable'] = 'armed_tripped'
            data['value_map'] = {
                'True': STATE_TRIPPED,
                'False': STATE_NOT_TRIPPED
            }
            data['initial_state'] = (
                'True' if str(self._device_data.get('armedtripped')) == '1'
                else 'False')
            data['state_attributes'] = self.get_common_state_attrs()
            # If this device also has a tripped property we hide the armed_
            # tripped property to avoid clutter
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('armed_tripped', self.is_trippable))
            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_CHILD_SENSORS,
                    ATTR_DISCOVERED: data})

        if self.has_battery and not self.should_exclude_child('battery'):
            data = {}
            data['name'] = (
                self._config.get('battery', {})
                .get('name', self._name + ' Battery'))
            data['parent_entity_id'] = self.entity_id
            data['watched_variable'] = ATTR_BATTERY_LEVEL
            data['initial_state'] = self._device_data.get('batterylevel')
            data['unit_of_measurement'] = '%'
            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('battery'))
            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_CHILD_SENSORS,
                    ATTR_DISCOVERED: data})

        if self.has_humidity and not self.should_exclude_child('humidity'):
            data = {}
            data['name'] = (
                self._config.get('humidity', {}).get('name', self._name))
            data['parent_entity_id'] = self.entity_id
            data['watched_variable'] = 'humidity'
            data['initial_state'] = self._device_data.get('humidity')
            data['unit_of_measurement'] = '%'
            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('humidity'))
            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_CHILD_SENSORS,
                    ATTR_DISCOVERED: data})

        if self.has_lightlevel and not self.should_exclude_child('lightlevel'):
            data = {}
            data['name'] = (
                self._config.get('lightlevel', {}).get('name', self._name))
            data['parent_entity_id'] = self.entity_id
            data['watched_variable'] = 'light_level'
            data['initial_state'] = self._device_data.get('light')
            data['unit_of_measurement'] = 'lux'
            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('lightlevel'))
            self._hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: DISCOVER_CHILD_SENSORS,
                ATTR_DISCOVERED: data})

        if self.is_armable and not self.should_exclude_child('arm_switch'):
            data = {}
            data['name'] = (
                self._config.get('arm_switch', {}).get('name', self._name))
            data['parent_entity_id'] = self.entity_id
            data['watched_variable'] = ATTR_ARMED
            data['parent_domain'] = DOMAIN
            data['parent_service'] = SERVICE_SET_VAL
            data['parent_action'] = 'set_value'
            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('arm_switch'))
            data['extra_data'] = {
                'vera_device_id': self._device_data.get('id'),
                'vera_variable': 'Armed'}

            data['initial_state'] = (
                'True' if str(self._device_data.get('armed')) == '1'
                else 'False')
            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: DISCOVER_CHILD_SWITCHES,
                    ATTR_DISCOVERED: data})

        if self.is_switchable and not self.should_exclude_child('switch'):
            data = {}
            data['name'] = (
                self._config.get('switch', {}).get('name', self._name))
            data['parent_entity_id'] = self.entity_id

            data['parent_domain'] = DOMAIN
            data['parent_service'] = SERVICE_SET_VAL

            data['parent_action'] = 'switch'
            data['watched_variable'] = 'status'
            data['extra_data'] = {
                'vera_device_id': self._device_data.get('id'),
                'vera_variable': 'Target'}

            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('switch'))
            data['initial_state'] = (
                'True' if str(self._device_data.get('status')) == '1'
                else 'False')

            child_type = DISCOVER_CHILD_SWITCHES
            if self._config.get('switch', {}).get('is_light', False):
                child_type = DISCOVER_CHILD_LIGHTS

            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: child_type,
                    ATTR_DISCOVERED: data})

        if self.is_dimmable and not self.should_exclude_child('switch'):
            data = {}
            data['name'] = (
                self._config.get('switch', {}).get('name', self._name))
            data['parent_entity_id'] = self.entity_id

            data['parent_domain'] = DOMAIN
            data['parent_service'] = SERVICE_SET_VAL
            data['parent_action'] = 'dim'
            data['light_type'] = 'dimmer'
            data['state_attributes'] = self.get_common_state_attrs()
            data['state_attributes'][ATTR_HIDDEN] = (
                self.is_child_hidden('switch'))
            data['state_attributes']['level'] = self._device_data.get('level')

            brightness = self.get_brightness()
            data['state_attributes'][ATTR_BRIGHTNESS] = brightness
            data['watched_variable'] = ATTR_BRIGHTNESS
            data['extra_data'] = {
                'vera_device_id': self._device_data.get('id'),
                'vera_variable': 'LoadLevelTarget'}

            data['initial_state'] = (
                'True' if str(self._device_data.get('status')) == '1'
                else 'False')
            data['initial_brightness'] = brightness

            child_type = DISCOVER_CHILD_SWITCHES
            if self._config.get('switch', {}).get('is_light', True):
                child_type = DISCOVER_CHILD_LIGHTS

            self._hass.bus.fire(
                EVENT_PLATFORM_DISCOVERED, {
                    ATTR_SERVICE: child_type,
                    ATTR_DISCOVERED: data})

    def get_common_state_attrs(self):
        """ This is a convenience method that returns an a dict that
        contains state attributes that are common to all child devices.
        These state attributes will be passed to child devices on discovery
        and the appended to the child device state attributes """
        attrs = {}
        attrs['vera_id'] = self._device_data.get('id')
        return attrs

    def should_exclude_child(self, type_name):
        """ Returns true if a particular child entity should not be discovered.
        This could be due to user config or that the variable is already being
        montiroed by the top level entity and creating a new child is
        unnecessary """
        if type_name == self._state_variable:
            return True
        elif (type_name == 'switch' and
              self._state_variable == 'status'):
            return True
        elif (type_name == 'switch' and
              self.is_dimmable and
              self._state_variable == 'level'):
            return True
        elif (type_name == 'lightlevel' and
              self._state_variable == 'light'):
            return True
        elif (type_name == 'armedtripped' and
              self._state_variable == 'armed_tripped'):
            return True

        return self._config.get(type_name, {}).get('exclude', False)

    def is_child_hidden(self, type_name, default_value=False):
        """ Returns true if a child entity should be hidden on the states
        UI """
        return self._config.get(type_name, {}).get('hidden', default_value)

    def get_brightness(self):
        """ Converts the Vera level property for dimmable lights from a
        percentage to the 0 - 255 scale used by HA """
        percent = int(self._device_data.get('level', 100))
        brightness = 0
        if percent > 0:
            brightness = round(percent * 2.55)

        return int(brightness)
