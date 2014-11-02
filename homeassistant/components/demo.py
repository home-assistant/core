"""
homeassistant.components.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sets up a demo environment that mimics interaction with devices
"""
import random

import homeassistant as ha
import homeassistant.components.group as group
from homeassistant.components import (SERVICE_TURN_ON, SERVICE_TURN_OFF,
                                      STATE_ON, STATE_OFF, get_component,
                                      extract_entity_ids)
from homeassistant.components.light import (ATTR_XY_COLOR, ATTR_BRIGHTNESS,
                                            GROUP_NAME_ALL_LIGHTS)
from homeassistant.util import split_entity_id

DOMAIN = "demo"

DEPENDENCIES = []


def setup(hass, config):
    """ Setup a demo environment. """

    if config[DOMAIN].get('hide_demo_state') != '1':
        hass.states.set('a.Demo_Mode', 'Enabled')

    light_colors = [
        [0.861, 0.3259],
        [0.6389, 0.3028],
        [0.1684, 0.0416]
    ]

    def mock_turn_on(service):
        """ Will fake the component has been turned on. """
        for entity_id in extract_entity_ids(hass, service):
            domain, _ = split_entity_id(entity_id)

            if domain == "light":
                data = {ATTR_BRIGHTNESS: 200,
                        ATTR_XY_COLOR: random.choice(light_colors)}
            else:
                data = None

            hass.states.set(entity_id, STATE_ON, data)

    def mock_turn_off(service):
        """ Will fake the component has been turned off. """
        for entity_id in extract_entity_ids(hass, service):
            hass.states.set(entity_id, STATE_OFF)

    # Setup sun
    if ha.CONF_LATITUDE not in config[ha.DOMAIN]:
        config[ha.DOMAIN][ha.CONF_LATITUDE] = '32.87336'

    if ha.CONF_LONGITUDE not in config[ha.DOMAIN]:
        config[ha.DOMAIN][ha.CONF_LONGITUDE] = '-117.22743'

    get_component('sun').setup(hass, config)

    # Setup fake lights
    lights = ['light.Bowl', 'light.Ceiling', 'light.TV_Back_light',
              'light.Bed_light']

    hass.services.register('light', SERVICE_TURN_ON, mock_turn_on)
    hass.services.register('light', SERVICE_TURN_OFF, mock_turn_off)

    mock_turn_on(ha.ServiceCall('light', SERVICE_TURN_ON,
                                {'entity_id': lights[0:2]}))
    mock_turn_off(ha.ServiceCall('light', SERVICE_TURN_OFF,
                                 {'entity_id': lights[2:]}))

    group.setup_group(hass, GROUP_NAME_ALL_LIGHTS, lights, False)

    # Setup Wemo
    wemos = ['wemo.AC', 'wemo.Christmas_Lights']

    hass.services.register('wemo', SERVICE_TURN_ON, mock_turn_on)
    hass.services.register('wemo', SERVICE_TURN_OFF, mock_turn_off)

    mock_turn_on(ha.ServiceCall('wemo', SERVICE_TURN_ON,
                                {'entity_id': wemos[0:1]}))
    mock_turn_off(ha.ServiceCall('wemo', SERVICE_TURN_OFF,
                                 {'entity_id': wemos[1:]}))

    # Setup room groups
    group.setup_group(hass, 'living_room', lights[0:3] + wemos[0:1])
    group.setup_group(hass, 'bedroom', [lights[3]] + wemos[1:])

    # Setup process
    hass.states.set("process.XBMC", STATE_ON)

    # Setup device tracker
    hass.states.set("device_tracker.Paulus", "home")
    hass.states.set("device_tracker.Anne_Therese", "not_home")
    hass.states.set("group.all_devices", "home",
                    {
                        "auto": True,
                        "entity_id": [
                            "device_tracker.Paulus",
                            "device_tracker.Anne_Therese"
                        ]
                    })

    # Setup chromecast
    hass.states.set("chromecast.Living_Rm", "Netflix",
                    {'friendly_name': 'Living Room'})

    return True
