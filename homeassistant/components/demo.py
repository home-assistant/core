"""
homeassistant.components.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sets up a demo environment that mimics interaction with devices
"""
import random
import time

import homeassistant as ha
import homeassistant.loader as loader
from homeassistant.helpers import extract_entity_ids
from homeassistant.const import (
    SERVICE_TURN_ON, SERVICE_TURN_OFF,
    STATE_ON, STATE_OFF, TEMP_CELCIUS,
    ATTR_ENTITY_PICTURE, ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT,
    CONF_LATITUDE, CONF_LONGITUDE)
from homeassistant.components.light import (
    ATTR_XY_COLOR, ATTR_RGB_COLOR, ATTR_BRIGHTNESS, GROUP_NAME_ALL_LIGHTS)
from homeassistant.components.thermostat import (
    ATTR_CURRENT_TEMPERATURE, ATTR_AWAY_MODE)
from homeassistant.util import split_entity_id, color_RGB_to_xy

DOMAIN = "demo"

DEPENDENCIES = []


def setup(hass, config):
    """ Setup a demo environment. """
    group = loader.get_component('group')
    configurator = loader.get_component('configurator')

    config.setdefault(ha.DOMAIN, {})
    config.setdefault(DOMAIN, {})

    if config[DOMAIN].get('hide_demo_state') != '1':
        hass.states.set('a.Demo_Mode', 'Enabled')

    light_colors = [
        [0.861, 0.3259],
        [0.6389, 0.3028],
        [0.1684, 0.0416]
    ]

    def mock_turn_on(service):
        """ Will fake the component has been turned on. """
        if service.data and ATTR_ENTITY_ID in service.data:
            entity_ids = extract_entity_ids(hass, service)
        else:
            entity_ids = hass.states.entity_ids(service.domain)

        for entity_id in entity_ids:
            domain, _ = split_entity_id(entity_id)

            if domain == "light":
                rgb_color = service.data.get(ATTR_RGB_COLOR)

                if rgb_color:
                    color = color_RGB_to_xy(
                        rgb_color[0], rgb_color[1], rgb_color[2])

                else:
                    cur_state = hass.states.get(entity_id)

                    # Use current color if available
                    if cur_state and cur_state.attributes.get(ATTR_XY_COLOR):
                        color = cur_state.attributes.get(ATTR_XY_COLOR)
                    else:
                        color = random.choice(light_colors)

                data = {
                    ATTR_BRIGHTNESS: service.data.get(ATTR_BRIGHTNESS, 200),
                    ATTR_XY_COLOR: color
                }
            else:
                data = None

            hass.states.set(entity_id, STATE_ON, data)

    def mock_turn_off(service):
        """ Will fake the component has been turned off. """
        if service.data and ATTR_ENTITY_ID in service.data:
            entity_ids = extract_entity_ids(hass, service)
        else:
            entity_ids = hass.states.entity_ids(service.domain)

        for entity_id in entity_ids:
            hass.states.set(entity_id, STATE_OFF)

    # Setup sun
    if CONF_LATITUDE not in config[ha.DOMAIN]:
        config[ha.DOMAIN][CONF_LATITUDE] = '32.87336'

    if CONF_LONGITUDE not in config[ha.DOMAIN]:
        config[ha.DOMAIN][CONF_LONGITUDE] = '-117.22743'

    loader.get_component('sun').setup(hass, config)

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

    # Setup switch
    switches = ['switch.AC', 'switch.Christmas_Lights']

    hass.services.register('switch', SERVICE_TURN_ON, mock_turn_on)
    hass.services.register('switch', SERVICE_TURN_OFF, mock_turn_off)

    mock_turn_on(ha.ServiceCall('switch', SERVICE_TURN_ON,
                                {'entity_id': switches[0:1]}))
    mock_turn_off(ha.ServiceCall('switch', SERVICE_TURN_OFF,
                                 {'entity_id': switches[1:]}))

    # Setup room groups
    group.setup_group(hass, 'living_room', lights[0:3] + switches[0:1])
    group.setup_group(hass, 'bedroom', [lights[3]] + switches[1:])

    # Setup process
    hass.states.set("process.XBMC", STATE_ON)

    # Setup device tracker
    hass.states.set("device_tracker.Paulus", "home",
                    {ATTR_ENTITY_PICTURE:
                     "http://graph.facebook.com/schoutsen/picture"})
    hass.states.set("device_tracker.Anne_Therese", "not_home",
                    {ATTR_ENTITY_PICTURE:
                     "http://graph.facebook.com/anne.t.frederiksen/picture"})

    hass.states.set("group.all_devices", "home",
                    {
                        "auto": True,
                        "entity_id": [
                            "device_tracker.Paulus",
                            "device_tracker.Anne_Therese"
                        ]
                    })

    # Setup chromecast
    hass.states.set("chromecast.Living_Rm", "Plex",
                    {'friendly_name': 'Living Room',
                     ATTR_ENTITY_PICTURE:
                     'http://graph.facebook.com/KillBillMovie/picture'})

    # Setup tellstick sensors
    hass.states.set("tellstick_sensor.Outside_temperature", "15.6",
                    {
                        'friendly_name': 'Outside temperature',
                        'unit_of_measurement': '°C'
                    })
    hass.states.set("tellstick_sensor.Outside_humidity", "54",
                    {
                        'friendly_name': 'Outside humidity',
                        'unit_of_measurement': '%'
                    })

    # Nest demo
    hass.states.set("thermostat.Nest", "23",
                    {
                        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELCIUS,
                        ATTR_CURRENT_TEMPERATURE: '18',
                        ATTR_AWAY_MODE: STATE_OFF
                    })

    configurator_ids = []

    def hue_configuration_callback(data):
        """ Fake callback, mark config as done. """
        time.sleep(2)

        # First time it is called, pretend it failed.
        if len(configurator_ids) == 1:
            configurator.notify_errors(
                hass, configurator_ids[0],
                "Failed to register, please try again.")

            configurator_ids.append(0)
        else:
            configurator.request_done(hass, configurator_ids[0])

    request_id = configurator.request_config(
        hass, "Philips Hue", hue_configuration_callback,
        description=("Press the button on the bridge to register Philips Hue "
                     "with Home Assistant."),
        description_image="/static/images/config_philips_hue.jpg",
        submit_caption="I have pressed the button"
    )

    configurator_ids.append(request_id)

    return True
