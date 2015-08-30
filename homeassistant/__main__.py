""" Starts home assistant. """
from __future__ import print_function

import sys
import os
import argparse
import importlib

from homeassistant import bootstrap
import homeassistant.config as config_util


def validate_python():
    """ Validate we're running the right Python version. """
    major, minor = sys.version_info[:2]

    if major < 3 or (major == 3 and minor < 4):
        print("Home Assistant requires atleast Python 3.4")
        sys.exit()


def ensure_pip():
    """ Validate pip is installed so we can install packages on demand. """
    if importlib.find_loader('pip') is None:
        print("Your Python installation did not bundle 'pip'")
        print("Home Assistant requires 'pip' to be installed.")
        print("Please install pip: "
              "https://pip.pypa.io/en/latest/installing.html")
        sys.exit()


def ensure_config_path(config_dir):
    """ Gets the path to the configuration file.
        Creates one if it not exists. """

    lib_dir = os.path.join(config_dir, 'lib')

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        if config_dir == config_util.get_default_config_dir():
            try:
                os.mkdir(config_dir)
            except OSError:
                print(('Fatal Error: Unable to create default configuration '
                       'directory {} ').format(config_dir))
                sys.exit()
        else:
            print(('Fatal Error: Specified configuration directory does '
                   'not exist {} ').format(config_dir))
            sys.exit()

    # Test if library directory exists
    if not os.path.isdir(lib_dir):
        try:
            os.mkdir(lib_dir)
        except OSError:
            print(('Fatal Error: Unable to create library '
                   'directory {} ').format(lib_dir))
            sys.exit()

    config_path = config_util.ensure_config_exists(config_dir)

    if config_path is None:
        print('Error getting configuration path')
        sys.exit()

    return config_path


def get_arguments():
    """ Get parsed passed in arguments. """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--config',
        metavar='path_to_config_dir',
        default=config_util.get_default_config_dir(),
        help="Directory that contains the Home Assistant configuration")
    parser.add_argument(
        '--demo-mode',
        action='store_true',
        help='Start Home Assistant in demo mode')
    parser.add_argument(
        '--open-ui',
        action='store_true',
        help='Open the webinterface in a browser')

    return parser.parse_args()


def main():
    """ Starts Home Assistant. """
    validate_python()

    args = get_arguments()

    config_dir = os.path.join(os.getcwd(), args.config)
    config_path = ensure_config_path(config_dir)

    if args.demo_mode:
        hass = bootstrap.from_config_dict({
            'frontend': {},
            'demo': {}
        }, config_dir=config_dir)
    else:
        hass = bootstrap.from_config_file(config_path)

    if args.open_ui:
        def open_browser(event):
            """ Open the webinterface in a browser. """
            if hass.config.api is not None:
                import webbrowser
                webbrowser.open(hass.config.api.base_url)
        from homeassistant.const import EVENT_HOMEASSISTANT_START
        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, open_browser)

    hass.start()
    hass.block_till_stopped()

if __name__ == "__main__":
    main()
