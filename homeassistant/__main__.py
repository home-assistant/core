""" Starts home assistant. """

import sys
import os
import argparse

try:
    from homeassistant import bootstrap

except ImportError:
    # This is to add support to load Home Assistant using
    # `python3 homeassistant` instead of `python3 -m homeassistant`

    # Insert the parent directory of this file into the module search path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from homeassistant import bootstrap


def main():
    """ Starts Home Assistant. Will create demo config if no config found. """
    tasks = ['serve', 'test']

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default="config",
        help="Directory that contains the Home Assistant configuration")

    parser.add_argument(
        '-t', '--task',
        default=tasks[0],
        choices=tasks,
        help="Task to execute. Defaults to serve.")

    args = parser.parse_args()

    if args.task == tasks[1]:
        # unittest does not like our command line arguments, remove them
        sys.argv[1:] = []

        import unittest

        unittest.main(module='homeassistant.test')

    else:
        config_path = os.path.join(args.config, 'home-assistant.conf')

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
