"""
homeassistant.components.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sets up a demo environment that mimics interaction with devices.
"""
import time

import homeassistant.bootstrap as bootstrap
import homeassistant.core as ha
import homeassistant.loader as loader
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM

DOMAIN = "demo"

DEPENDENCIES = ['conversation', 'introduction', 'zone']

COMPONENTS_WITH_DEMO_PLATFORM = [
    'alarm_control_panel',
    'binary_sensor',
    'camera',
    'device_tracker',
    'garage_door',
    'light',
    'lock',
    'media_player',
    'notify',
    'rollershutter',
    'sensor',
    'switch',
    'thermostat',
]


def setup(hass, config):
    """ Setup a demo environment. """
    group = loader.get_component('group')
    configurator = loader.get_component('configurator')

    config.setdefault(ha.DOMAIN, {})
    config.setdefault(DOMAIN, {})

    if config[DOMAIN].get('hide_demo_state') != 1:
        hass.states.set('a.Demo_Mode', 'Enabled')

    # Setup sun
    if not hass.config.latitude:
        hass.config.latitude = 32.87336

    if not hass.config.longitude:
        hass.config.longitude = 117.22743

    bootstrap.setup_component(hass, 'sun')

    # Setup demo platforms
    demo_config = config.copy()
    for component in COMPONENTS_WITH_DEMO_PLATFORM:
        demo_config[component] = {CONF_PLATFORM: 'demo'}
        bootstrap.setup_component(hass, component, demo_config)

    # Setup room groups
    lights = sorted(hass.states.entity_ids('light'))
    switches = sorted(hass.states.entity_ids('switch'))
    media_players = sorted(hass.states.entity_ids('media_player'))
    group.Group(hass, 'living room', [
        lights[2], lights[1], switches[0], media_players[1],
        'scene.romantic_lights'])
    group.Group(hass, 'bedroom', [lights[0], switches[1],
                                  media_players[0]])
    group.Group(hass, 'Rooms', [
        'group.living_room', 'group.bedroom',
        'scene.romantic_lights', 'rollershutter.kitchen_window',
        'rollershutter.living_room_window',
    ], view=True)

    # Setup scripts
    bootstrap.setup_component(
        hass, 'script',
        {'script': {
            'demo': {
                'alias': 'Toggle {}'.format(lights[0].split('.')[1]),
                'sequence': [{
                    'execute_service': 'light.turn_off',
                    'service_data': {ATTR_ENTITY_ID: lights[0]}
                }, {
                    'delay': {'seconds': 5}
                }, {
                    'execute_service': 'light.turn_on',
                    'service_data': {ATTR_ENTITY_ID: lights[0]}
                }, {
                    'delay': {'seconds': 5}
                }, {
                    'execute_service': 'light.turn_off',
                    'service_data': {ATTR_ENTITY_ID: lights[0]}
                }]
            }}})

    # Setup scenes
    bootstrap.setup_component(
        hass, 'scene',
        {'scene': [
            {'name': 'Romantic lights',
             'entities': {
                 lights[0]: True,
                 lights[1]: {'state': 'on', 'xy_color': [0.33, 0.66],
                             'brightness': 200},
             }},
            {'name': 'Switch on and off',
             'entities': {
                 switches[0]: True,
                 switches[1]: False,
             }},
            ]})

    # Setup configurator
    configurator_ids = []

    def hue_configuration_callback(data):
        """ Fake callback, mark config as done. """
        time.sleep(2)

        # First time it is called, pretend it failed.
        if len(configurator_ids) == 1:
            configurator.notify_errors(
                configurator_ids[0],
                "Failed to register, please try again.")

            configurator_ids.append(0)
        else:
            configurator.request_done(configurator_ids[0])

    request_id = configurator.request_config(
        hass, "Philips Hue", hue_configuration_callback,
        description=("Press the button on the bridge to register Philips Hue "
                     "with Home Assistant."),
        description_image="/static/images/config_philips_hue.jpg",
        submit_caption="I have pressed the button"
    )

    configurator_ids.append(request_id)

    return True
