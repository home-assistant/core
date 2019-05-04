"""Set up the demo environment that mimics interaction with devices."""
import asyncio
import logging
import time

from homeassistant import bootstrap
import homeassistant.core as ha
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START

DOMAIN = 'demo'
_LOGGER = logging.getLogger(__name__)
COMPONENTS_WITH_DEMO_PLATFORM = [
    'air_quality',
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


async def async_setup(hass, config):
    """Set up the demo environment."""
    if DOMAIN not in config:
        return True

    config.setdefault(ha.DOMAIN, {})
    config.setdefault(DOMAIN, {})

    # Set up demo platforms
    for component in COMPONENTS_WITH_DEMO_PLATFORM:
        hass.async_create_task(hass.helpers.discovery.async_load_platform(
            component, DOMAIN, {}, config,
        ))

    # Set up sun
    if not hass.config.latitude:
        hass.config.latitude = 32.87336

    if not hass.config.longitude:
        hass.config.longitude = 117.22743

    tasks = [
        bootstrap.async_setup_component(hass, 'sun', config)
    ]

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

    results = await asyncio.gather(*tasks)

    if any(not result for result in results):
        return False

    # Set up example persistent notification
    hass.components.persistent_notification.async_create(
        'This is an example of a persistent notification.',
        title='Example Notification')

    # Set up configurator
    configurator_ids = []
    configurator = hass.components.configurator

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

    request_id = configurator.async_request_config(
        "Philips Hue", hue_configuration_callback,
        description=("Press the button on the bridge to register Philips "
                     "Hue with Home Assistant."),
        description_image="/static/images/config_philips_hue.jpg",
        fields=[{'id': 'username', 'name': 'Username'}],
        submit_caption="I have pressed the button"
    )
    configurator_ids.append(request_id)

    async def demo_start_listener(_event):
        """Finish set up."""
        await finish_setup(hass, config)

    hass.bus.async_listen(EVENT_HOMEASSISTANT_START, demo_start_listener)

    return True


async def finish_setup(hass, config):
    """Finish set up once demo platforms are set up."""
    lights = sorted(hass.states.async_entity_ids('light'))
    switches = sorted(hass.states.async_entity_ids('switch'))

    # Set up history graph
    await bootstrap.async_setup_component(
        hass, 'history_graph',
        {'history_graph': {'switches': {
            'name': 'Recent Switches',
            'entities': switches,
            'hours_to_show': 1,
            'refresh': 60
        }}}
    )

    # Set up scripts
    await bootstrap.async_setup_component(
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
            }}})

    # Set up scenes
    await bootstrap.async_setup_component(
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
