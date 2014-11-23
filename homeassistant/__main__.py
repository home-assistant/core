""" Starts home assistant. """

import sys
import os
import argparse
import importlib

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

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default="config",
        help="Directory that contains the Home Assistant configuration")

    args = parser.parse_args()

    # Validate that all core dependencies are installed
    import_fail = False

    for module in ['requests']:
        try:
            importlib.import_module(module)
        except ImportError:
            import_fail = True
            print(
                'Fatal Error: Unable to find dependency {}'.format(module))

    if import_fail:
        print(("Install dependencies by running: "
               "pip3 install -r requirements.txt"))
        exit()

    # Test if configuration directory exists
    config_dir = os.path.join(os.getcwd(), args.config)

    if not os.path.isdir(config_dir):
        print(('Fatal Error: Unable to find specified configuration '
               'directory {} ').format(config_dir))
        sys.exit()

    config_path = os.path.join(config_dir, 'home-assistant.conf')

    # Ensure a config file exists to make first time usage easier
    if not os.path.isfile(config_path):
        try:
            with open(config_path, 'w') as conf:
                conf.write("[http]\n")
                conf.write("api_password=password\n\n")
                conf.write("[demo]\n")
        except IOError:
            print(('Fatal Error: No configuration file found and unable '
                   'to write a default one to {}').format(config_path))
            sys.exit()

    hass = bootstrap.from_config_file(config_path)
    hass.start()
    hass.block_till_stopped()

if __name__ == "__main__":
    main()
