""" Starts home assistant. """
from __future__ import print_function

import sys
import os
import argparse
import importlib


def validate_python():
    """ Validate we're running the right Python version. """
    major, minor = sys.version_info[:2]

    if major < 3 or (major == 3 and minor < 4):
        print("Home Assistant requires atleast Python 3.4")
        sys.exit()


def validate_dependencies():
    """ Validate all dependencies that HA uses. """
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
        sys.exit()


def ensure_path_and_load_bootstrap():
    """ Ensure sys load path is correct and load Home Assistant bootstrap. """
    try:
        from homeassistant import bootstrap

    except ImportError:
        # This is to add support to load Home Assistant using
        # `python3 homeassistant` instead of `python3 -m homeassistant`

        # Insert the parent directory of this file into the module search path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

        from homeassistant import bootstrap

    return bootstrap


def validate_git_submodules():
    """ Validate the git submodules are cloned. """
    try:
        # pylint: disable=no-name-in-module, unused-variable
        from homeassistant.external.noop import WORKING  # noqa
    except ImportError:
        print("Repository submodules have not been initialized")
        print("Please run: git submodule update --init --recursive")
        sys.exit()


def ensure_config_path(config_dir):
    """ Gets the path to the configuration file.
        Creates one if it not exists. """

    # Test if configuration directory exists
    if not os.path.isdir(config_dir):
        print(('Fatal Error: Unable to find specified configuration '
               'directory {} ').format(config_dir))
        sys.exit()

    import homeassistant.config as config_util

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
        default="config",
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
    validate_dependencies()

    bootstrap = ensure_path_and_load_bootstrap()

    validate_git_submodules()

    args = get_arguments()

    config_dir = os.path.join(os.getcwd(), args.config)
    config_path = ensure_config_path(config_dir)

    if args.demo_mode:
        from homeassistant.components import http, demo

        # Demo mode only requires http and demo components.
        hass = bootstrap.from_config_dict({
            http.DOMAIN: {},
            demo.DOMAIN: {}
        })
    else:
        hass = bootstrap.from_config_file(config_path)

    if args.open_ui:
        from homeassistant.const import EVENT_HOMEASSISTANT_START

        def open_browser(event):
            """ Open the webinterface in a browser. """
            if hass.local_api is not None:
                import webbrowser
                webbrowser.open(hass.local_api.base_url)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_START, open_browser)

    hass.start()
    hass.block_till_stopped()

if __name__ == "__main__":
    main()
