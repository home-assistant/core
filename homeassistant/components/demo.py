"""
Set up the demo environment that mimics interaction with devices.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import asyncio
import time

from homeassistant import bootstrap
import homeassistant.core as ha
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM

DEPENDENCIES = ['conversation', 'introduction', 'zone']
DOMAIN = 'demo'

COMPONENTS_WITH_DEMO_PLATFORM = [
    'alarm_control_panel',
    'binary_sensor',
    'calendar',
    'camera',
    'climate',
    'cover',
    'device_tracker',
    'fan',
    'image_processing',
    'light',
    'lock',
    'media_player',
    'notify',
    'sensor',
    'switch',
    'tts',
    'mailbox',
]


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the demo environment."""
    group = hass.components.group
    configurator = hass.components.configurator
    persistent_notification = hass.components.persistent_notification

    config.setdefault(ha.DOMAIN, {})
    config.setdefault(DOMAIN, {})

    if config[DOMAIN].get('hide_demo_state') != 1:
        hass.states.async_set('a.Demo_Mode', 'Enabled')

    # Setup sun
    if not hass.config.latitude:
        hass.config.latitude = 32.87336

    if not hass.config.longitude:
        hass.config.longitude = 117.22743

    tasks = [
        bootstrap.async_setup_component(hass, 'sun')
    ]

    # Set up demo platforms
    demo_config = config.copy()
    for component in COMPONENTS_WITH_DEMO_PLATFORM:
        demo_config[component] = {CONF_PLATFORM: 'demo'}
        tasks.append(
            bootstrap.async_setup_component(hass, component, demo_config))

    # Set up input select
    tasks.append(bootstrap.async_setup_component(
        hass, 'input_select',
        {'input_select':
         {'living_room_preset': {'options': ['Visitors',
                                             'Visitors with kids',
                                             'Home Alone']},
          'who_cooks': {'icon': 'mdi:panda',
                        'initial': 'Anne Therese',
                        'name': 'Cook today',
                        'options': ['Paulus', 'Anne Therese']}}}))
    # Set up input boolean
    tasks.append(bootstrap.async_setup_component(
        hass, 'input_boolean',
        {'input_boolean': {'notify': {
            'icon': 'mdi:car',
            'initial': False,
            'name': 'Notify Anne Therese is home'}}}))

    # Set up input boolean
    tasks.append(bootstrap.async_setup_component(
        hass, 'input_number',
        {'input_number': {
            'noise_allowance': {'icon': 'mdi:bell-ring',
                                'min': 0,
                                'max': 10,
                                'name': 'Allowed Noise',
                                'unit_of_measurement': 'dB'}}}))

    # Set up weblink
    tasks.append(bootstrap.async_setup_component(
        hass, 'weblink',
        {'weblink': {'entities': [{'name': 'Router',
                                   'url': 'http://192.168.1.1'}]}}))

    results = yield from asyncio.gather(*tasks, loop=hass.loop)

    if any(not result for result in results):
        return False

    # Set up example persistent notification
    persistent_notification.async_create(
        'This is an example of a persistent notification.',
        title='Example Notification')

    # Set up room groups
    lights = sorted(hass.states.async_entity_ids('light'))
    switches = sorted(hass.states.async_entity_ids('switch'))
    media_players = sorted(hass.states.async_entity_ids('media_player'))

    tasks2 = []

    # Set up history graph
    tasks2.append(bootstrap.async_setup_component(
        hass, 'history_graph',
        {'history_graph': {'switches': {
            'name': 'Recent Switches',
            'entities': switches,
            'hours_to_show': 1,
            'refresh': 60
        }}}
    ))

    # Set up scripts
    tasks2.append(bootstrap.async_setup_component(
        hass, 'script',
        {'script': {
            'demo': {
                'alias': 'Toggle {}'.format(lights[0].split('.')[1]),
                'sequence': [{
                    'service': 'light.turn_off',
                    'data': {ATTR_ENTITY_ID: lights[0]}
                }, {
                    'delay': {'seconds': 5}
                }, {
                    'service': 'light.turn_on',
                    'data': {ATTR_ENTITY_ID: lights[0]}
                }, {
                    'delay': {'seconds': 5}
                }, {
                    'service': 'light.turn_off',
                    'data': {ATTR_ENTITY_ID: lights[0]}
                }]
            }}}))

    # Set up scenes
    tasks2.append(bootstrap.async_setup_component(
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
            ]}))

    tasks2.append(group.Group.async_create_group(hass, 'Living Room', [
        lights[1], switches[0], 'input_select.living_room_preset',
        'cover.living_room_window', media_players[1],
        'scene.romantic_lights']))
    tasks2.append(group.Group.async_create_group(hass, 'Bedroom', [
        lights[0], switches[1], media_players[0],
        'input_number.noise_allowance']))
    tasks2.append(group.Group.async_create_group(hass, 'Kitchen', [
        lights[2], 'cover.kitchen_window', 'lock.kitchen_door']))
    tasks2.append(group.Group.async_create_group(hass, 'Doors', [
        'lock.front_door', 'lock.kitchen_door',
        'garage_door.right_garage_door', 'garage_door.left_garage_door']))
    tasks2.append(group.Group.async_create_group(hass, 'Automations', [
        'input_select.who_cooks', 'input_boolean.notify', ]))
    tasks2.append(group.Group.async_create_group(hass, 'People', [
        'device_tracker.demo_anne_therese', 'device_tracker.demo_home_boy',
        'device_tracker.demo_paulus']))
    tasks2.append(group.Group.async_create_group(hass, 'Downstairs', [
        'group.living_room', 'group.kitchen',
        'scene.romantic_lights', 'cover.kitchen_window',
        'cover.living_room_window', 'group.doors',
        'climate.ecobee',
    ], view=True))

    results = yield from asyncio.gather(*tasks2, loop=hass.loop)

    if any(not result for result in results):
        return False

    # Set up configurator
    configurator_ids = []

    def hue_configuration_callback(data):
        """Fake callback, mark config as done."""
        time.sleep(2)

        # First time it is called, pretend it failed.
        if len(configurator_ids) == 1:
            configurator.notify_errors(
                configurator_ids[0],
                "Failed to register, please try again.")

            configurator_ids.append(0)
        else:
            configurator.request_done(configurator_ids[0])

    def setup_configurator():
        """Set up a configurator."""
        request_id = configurator.request_config(
            "Philips Hue", hue_configuration_callback,
            description=("Press the button on the bridge to register Philips "
                         "Hue with Home Assistant."),
            description_image="/static/images/config_philips_hue.jpg",
            fields=[{'id': 'username', 'name': 'Username'}],
            submit_caption="I have pressed the button"
        )
        configurator_ids.append(request_id)

    hass.async_add_job(setup_configurator)

    return True
