""" Starts home assistant. """

import sys
import os

import homeassistant
import homeassistant.bootstrap

# Within Docker we load the config from a different path
if '--docker' in sys.argv:
    config_path = '/config/home-assistant.conf'
else:
    config_path = 'config/home-assistant.conf'

# Ensure a config file exists to make first time usage easier
if not os.path.isfile(config_path):
    with open(config_path, 'w') as conf:
        conf.write("[http]\n")
        conf.write("api_password=password\n")

hass = homeassistant.bootstrap.from_config_file(config_path)
hass.start()
hass.block_till_stopped()
