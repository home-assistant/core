""" Starts home assistant. """

import sys
import os

try:
    from homeassistant import bootstrap

except ImportError:
    # This is to add support to load Home Assistant using
    # `python3 homeassistant` instead of `python3 -m homeassistant`

    # Insert the parent directory of this file into the module search path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from homeassistant import bootstrap


ARG_RUN_TESTS = "--run-tests"
ARG_DOCKER = '--docker'


def main():
    """ Starts Home Assistant. Will create demo config if no config found. """

    # Do we want to run the tests?
    if ARG_RUN_TESTS in sys.argv:
        sys.argv.remove(ARG_RUN_TESTS)

        import unittest

        unittest.main(module='homeassistant.test')

    # Within Docker we load the config from a different path
    if ARG_DOCKER in sys.argv:
        config_path = '/config/home-assistant.conf'
    else:
        config_path = 'config/home-assistant.conf'

    # Ensure a config file exists to make first time usage easier
    if not os.path.isfile(config_path):
        with open(config_path, 'w') as conf:
            conf.write("[http]\n")
            conf.write("api_password=password\n\n")
            conf.write("[demo]\n")

    hass = bootstrap.from_config_file(config_path)
    hass.start()
    hass.block_till_stopped()

if __name__ == "__main__":
    main()
