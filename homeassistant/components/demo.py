"""
homeassistant.components.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sets up a demo environment that mimics interaction with devices
"""
import time

import homeassistant as ha
import homeassistant.bootstrap as bootstrap
import homeassistant.loader as loader
from homeassistant.const import (
    CONF_PLATFORM, ATTR_ENTITY_PICTURE, STATE_ON,
    CONF_LATITUDE, CONF_LONGITUDE)

DOMAIN = "demo"

DEPENDENCIES = []

COMPONENTS_WITH_DEMO_PLATFORM = [
    'switch', 'light', 'thermostat', 'sensor', 'media_player']


def setup(hass, config):
    """ Setup a demo environment. """
    group = loader.get_component('group')
    configurator = loader.get_component('configurator')

    config.setdefault(ha.DOMAIN, {})
    config.setdefault(DOMAIN, {})

    if config[DOMAIN].get('hide_demo_state') != '1':
        hass.states.set('a.Demo_Mode', 'Enabled')

    # Setup sun
    if CONF_LATITUDE not in config[ha.DOMAIN]:
        config[ha.DOMAIN][CONF_LATITUDE] = '32.87336'

    if CONF_LONGITUDE not in config[ha.DOMAIN]:
        config[ha.DOMAIN][CONF_LONGITUDE] = '-117.22743'

    loader.get_component('sun').setup(hass, config)

    # Setup demo platforms
    for component in COMPONENTS_WITH_DEMO_PLATFORM:
        bootstrap.setup_component(
            hass, component, {component: {CONF_PLATFORM: 'demo'}})

    # Setup room groups
    lights = hass.states.entity_ids('light')
    switches = hass.states.entity_ids('switch')
    group.setup_group(hass, 'living room', [lights[0], lights[1], switches[0]])
    group.setup_group(hass, 'bedroom', [lights[2], switches[1]])

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
