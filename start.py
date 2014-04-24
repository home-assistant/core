""" Starts home assistant with all possible functionality. """

import homeassistant
import homeassistant.bootstrap

homeassistant.bootstrap.from_config_file("home-assistant.conf").start()
