""" Starts home assistant with all possible functionality. """

import homeassistant
import homeassistant.bootstrap

hass = homeassistant.bootstrap.from_config_file("config/home-assistant.conf")
hass.start()
hass.block_till_stopped()
