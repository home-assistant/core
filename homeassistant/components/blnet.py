"""
Connect to a BL-NET via it's web interface and read and write data
TODO: as component
"""
import logging

import voluptuous as vol
from pyblnet import BLNET, test_blnet
import asyncio
from homeassistant.helpers.discovery import load_platform

from homeassistant.const import (
    CONF_RESOURCE, STATE_UNKNOWN, CONF_PASSWORD, CONF_SCAN_INTERVAL)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'blnet'

CONF_NODE = 'can_node'
# means don't change current setting 
# for example if there is only one UVR1611 connected
DEFAULT_NODE = -1 
# scan every 6 minutes per default
DEFAULT_SCAN_INTERVAL = 360

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NODE, default=DEFAULT_NODE): cv.positive_int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int
        })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the BLNET component"""
    config = config[DOMAIN]
    resource = config.get(CONF_RESOURCE)
    password = config.get(CONF_PASSWORD)
    can_node = config.get(CONF_NODE)
    scan_interval = config.get(CONF_SCAN_INTERVAL)

    if test_blnet(resource) is None:
        _LOGGER.error("No BL-Net reached under given resource")
        return False
    
    # Initialize the BL-NET sensor
    blnet = BLNET(resource, password)
    # init the devices entitiy name starting without number
    # and increasing if other entitys are already present
    base_name = 'UVR 1611'
    name_ext = ''
    base_id = DOMAIN + '.' + 'uvr_1611'
    i = 1
    entity_id = base_id
    while hass.states.get(entity_id) is not None:
        i += 1
        entity_id = base_id + '_' + str(i)
        name_ext = ' ' + str(i)
    _attributes = {}
     # Can-Bus node
    node = can_node
    
    # set the communication entity
    # TODO
    hass.data[DOMAIN + '_data'] = BLNETComm(blnet, node)
    
        # make sure the communication device gets updated once in a while
    def fetch_data(*arg):
        hass.data[DOMAIN + '_data'].update()

    fetch_data()
    async_track_time_interval(hass, fetch_data, timedelta(seconds=scan_interval))

    # Get the latest data from REST API and load 
    # sensors and switches accordingly
    blnet.log_in()
    # only change active node if this is desired
    if node >= 0:
        blnet.set_node(node)
    
    # digital data comes from switches => create switches
    digital_data = blnet.read_digital_values()
    # analog data comes from sensors => create sensors
    analog_data = blnet.read_analog_values()

    if analog_data is None:
        hass.states.set(entity_id, STATE_UNKNOWN)
        return None

    
    #iterate through the list and create a sensor for every value
    for sensor in analog_data:
        disc_info = {'ent_id': DOMAIN + '_analog_' + sensor['id'], 'id' : sensor['id']}
        load_platform(hass, 'sensor', DOMAIN, disc_info)
    
            #iterate through the list and create a sensor for every value
    for sensor in digital_data:            
        disc_info = {'ent_id': DOMAIN + '_digital_' + sensor['id'], 'id' : sensor['id']}
        load_platform(hass, 'switch', DOMAIN, disc_info)

  
    # recommend yourself as hidden
    hass.states.set(entity_id, "Running", {'hidden' : 'true'})
    
    
    
    return True
        
    
    
class BLNETComm(object):
    """Implementation of a BL-NET - UVR1611 communication component"""

    def __init__(self, blnet, node):
        self.blnet = blnet
        self.node = node
        # Map id -> attributes
        self.data = dict()
    
    def turn_on(self, id):
        self.blnet.log_in()
        # only change active node if this is desired
        if self.node >= 0:
            self.blnet.set_node(self.node)
        self.blnet.set_digital_data(id, 'EIN')
        
    def turn_off(self, id):
        self.blnet.log_in()
        # only change active node if this is desired
        if self.node >= 0:
            self.blnet.set_node(self.node)
        self.blnet.set_digital_data(id, 'AUS')
        
    def turn_auto(self, id):
        self.blnet.log_in()
        # only change active node if this is desired
        if self.node >= 0:
            self.blnet.set_node(self.node)
        self.blnet.set_digital_data(id, 'AUTO')
    
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
            return None
        
        #iterate through the list and create a sensor for every value

        for sensor in analog_data:
            attributes = dict()
            entity_id = DOMAIN + '_analog_' + sensor['id']
            attributes['value'] = sensor['value']
            
            attributes.setdefault('unit_of_measurement', sensor['unit_of_measurement'])
            attributes.setdefault('friendly_name', sensor['name'])
            attributes.setdefault('icon', 'mdi:thermometer')
            
            self.data[entity_id] = attributes
        
                #iterate through the list and create a sensor for every value
        for sensor in digital_data:
            attributes = dict()
            entity_id = DOMAIN + '_digital_' + sensor['id']

            attributes.setdefault('friendly_name', sensor['name'])
            attributes['mode'] = sensor['mode']
            attributes['value'] = sensor['value']
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
                
            
            self.data[entity_id] = attributes

