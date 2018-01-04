"""
Connect to a BL-NET via it's web interface and read and write data
TODO: as platform
"""
import logging

import voluptuous as vol
from pyblnet import BLNET, test_blnet
import asyncio

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_RESOURCE, STATE_UNKNOWN, CONF_PASSWORD)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_NODE = 'can_node'
# means don't change current setting 
# for example if there is only one UVR1611 connected
DEFAULT_NODE = -1 


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NODE, default=DEFAULT_NODE): cv.positive_int
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the BLNET component"""
    resource = config.get(CONF_RESOURCE)
    password = config.get(CONF_PASSWORD)
    can_node = config.get(CONF_NODE)

    if test_blnet(resource) is None:
        _LOGGER.error("No BL-Net reached under given resource")
        return False

    add_devices([BLNETComponent(hass, BLNET(resource, password), can_node)])


class BLNETComponent(Entity):
    """Implementation of a BL-NET - UVR1611 sensor and switch component."""

    def __init__(self, hass, blnet, node):
        """Initialize the BL-NET sensor."""
        self._hass = hass
        self.blnet = blnet
        # init the devices entitiy name starting without number
        # and increasing if other entitys are already present
        base_name = 'UVR 1611'
        name_ext = ''
        base_id = 'sensor.' + 'uvr_1611'
        i = 1
        self.entity_id = base_id
        while hass.states.get(self.entity_id) is not None:
            i += 1
            self.entity_id = base_id + '_' + str(i)
            name_ext = ' ' + str(i)
        self._attributes = {}
        self._state = STATE_UNKNOWN
        self._name = base_name + name_ext
         # Can-Bus node
        self.node = node
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state
    
    def update(self):
        """Get the latest data from REST API and update the state."""
        self.blnet.log_in()
        # only change active node if this is desired
        if self.node >= 0:
            self.blnet.set_node(self.node)
        
        # digital data comes from switches => create switches
        digital_data = self.blnet.read_digital_values()
        # analog data comes from sensors => create sensors
        analog_data = self.blnet.read_analog_values()

        if analog_data is None:
            self._state = STATE_UNKNOWN
            return None
    
        # create a list storing all created sensors
        sensor_list = []
        
        #iterate through the list and create a sensor for every value
        for sensor in analog_data:
            entity_id = self.entity_id + '_analog_' + sensor['id']
            value = sensor['value']
            attributes = {
                'unit_of_measurement' : sensor['unit_of_measurement'],
                'friendly_name' : sensor['name'],
                'icon' : 'mdi:thermometer'
                }
            
            self._hass.states.set(entity_id, value, attributes)
            sensor_list.append(entity_id)
        
                #iterate through the list and create a sensor for every value
        for sensor in digital_data:
            entity_id = self.entity_id + '_digital_' + sensor['id']
            attributes = {
                'friendly_name' : sensor['name'],
                'mode' : sensor['mode']
                }
            value = sensor['value']
            # Change the symbol according to current mode and setting
            # Automated switch => gear symbol
            if sensor['mode'] == 'AUTO':
                attributes['icon'] = 'mdi:settings'
            # Nonautomated switch, toggled on => switch on
            elif value == 'EIN':
                attributes['icon'] = 'mdi:toggle-switch'
            # Nonautomated switch, toggled off => switch off
            else:
                attributes['icon'] =  'mdi:toggle-switch-off'
                
            
            self._hass.states.set(entity_id, value, attributes)
            sensor_list.append(entity_id)

        self._hass.states.set('group.uvr1611_data_logger', 'Running', {'entity_id': sensor_list, 'friendly_name': self._name, 'icon':'mdi:radiator'})
        
        # recommend yourself as hidden
        self._attributes['hidden'] = 'true'
            
        
    @property
    def state_attributes(self):
        """Return the attributes of the entity.

           Provide the BL-NET data
        """

        return self._attributes

'''
class BLNETSwitch(SwitchDevice):
    """Representation of a switch that toggles a digital output of the UVR1611."""

    def __init__(self, name, blnet_id):
        """Initialize the MQTT switch."""
        self._state = False
        self._name = name
        self.blnet_id = blnet_id

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def available(self) -> bool:
        """Return if switch is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if we do optimistic updates."""
        return self._optimistic

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the device on.
        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_on, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = True
            self.async_schedule_update_ha_state()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the device off.
        This method is a coroutine.
        """
        mqtt.async_publish(
            self.hass, self._command_topic, self._payload_off, self._qos,
            self._retain)
        if self._optimistic:
            # Optimistically assume that switch has changed state.
            self._state = False
            self.async_schedule_update_ha_state()
'''